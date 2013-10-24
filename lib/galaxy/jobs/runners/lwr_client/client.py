import os
import shutil
import simplejson
from simplejson import dumps
from time import sleep

from .destination import submit_params

CACHE_WAIT_SECONDS = 3
MAX_RETRY_COUNT = 5
RETRY_SLEEP_TIME = 0.1


class parseJson(object):

    def __call__(self, func):
        def replacement(*args, **kwargs):
            response = func(*args, **kwargs)
            return simplejson.loads(response)
        return replacement


class retry(object):

    def __call__(self, func):

        def replacement(*args, **kwargs):
            max_count = MAX_RETRY_COUNT
            count = 0
            while True:
                count += 1
                try:
                    return func(*args, **kwargs)
                except:
                    if count >= max_count:
                        raise
                    else:
                        sleep(RETRY_SLEEP_TIME)
                        continue

        return replacement


class OutputNotFoundException(Exception):

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return "No remote output found for path %s" % self.path


class Client(object):
    """
    Objects of this client class perform low-level communication with a remote LWR server.

    **Parameters**

    destination_params : dict or str
        connection parameters, either url with dict containing url (and optionally `private_token`).
    job_id : str
        Galaxy job/task id.
    """

    def __init__(self, destination_params, job_id, job_manager_interface):
        self.job_manager_interface = job_manager_interface
        self.destination_params = destination_params
        self.job_id = job_id

        self.default_file_action = self.destination_params.get("default_file_action", "transfer")
        self.action_config_path = self.destination_params.get("file_action_config", None)

    def _raw_execute(self, command, args={}, data=None, input_path=None, output_path=None):
        return self.job_manager_interface.execute(command, args, data, input_path, output_path)

    @property
    def _submit_params(self):
        return submit_params(self.destination_params)

    @parseJson()
    def input_path(self, path, input_type, name=None):
        args = {"job_id": self.job_id, "name": name, "input_type": input_type}
        return self._raw_execute('input_path', args)

    def put_file(self, path, input_type, name=None, contents=None, action='transfer'):
        if not name:
            name = os.path.basename(path)
        args = {"job_id": self.job_id, "name": name, "input_type": input_type}
        input_path = path
        if contents:
            input_path = None
        if action == 'transfer':
            return self._upload_file(args, contents, input_path)
        elif action == 'copy':
            lwr_path = self._raw_execute('input_path', args)
            self._copy(path, lwr_path)
            return {'path': lwr_path}

    @parseJson()
    def _upload_file(self, args, contents, input_path):
        return self._raw_execute(self._upload_file_action(args), args, contents, input_path)

    def _upload_file_action(self, args):
        ## Hack for backward compatibility, instead of using new upload_file
        ## path. Use old paths.
        input_type = args['input_type']
        action = {
            'input': 'upload_input',
            'input_extra': 'upload_extra_input',
            'config': 'upload_config_file',
            'work_dir': 'upload_working_directory_file',
            'tool': 'upload_tool_file'
        }[input_type]
        del args['input_type']
        return action

    @parseJson()
    def _get_output_type(self, name):
        return self._raw_execute("get_output_type", {"name": name,
                                                     "job_id": self.job_id})

    def fetch_output(self, path, working_directory, action='transfer'):
        """
        Download an output dataset from the remote server.

        **Parameters**

        path : str
            Local path of the dataset.
        working_directory : str
            Local working_directory for the job.
        """
        name = os.path.basename(path)
        output_type = self._get_output_type(name)

        if output_type == "none":
            # Just make sure the file was created.
            if not os.path.exists(path):
                raise OutputNotFoundException(path)
            return

        output_path = self.__output_path(path, name, working_directory, output_type)
        self.__populate_output_path(name, output_path, output_type, action)

    def __populate_output_path(self, name, output_path, output_type, action):
        if action == 'transfer':
            self.__raw_download_output(name, self.job_id, output_type, output_path)
        elif action == 'copy':
            lwr_path = self._output_path(name, self.job_id, output_type)['path']
            self._copy(lwr_path, output_path)

    def __output_path(self, path, name, working_directory, output_type):
        """
        Preconditions: output_type is not 'none'.
        """
        if output_type == "direct":
            output_path = path
        elif output_type == "task":
            output_path = os.path.join(working_directory, name)
        else:
            raise Exception("Unknown output_type returned from LWR server %s" % output_type)
        return output_path

    def fetch_work_dir_output(self, source, working_directory, output_path, action='transfer'):
        """
        Download an output dataset specified with from_work_dir from the
        remote server.

        **Parameters**

        source : str
            Path in job's working_directory to find output in.
        working_directory : str
            Local working_directory for the job.
        output_path : str
            Full path to output dataset.
        """
        output = open(output_path, "wb")
        name = os.path.basename(source)
        if action == 'transfer':
            self.__raw_download_output(name, self.job_id, "work_dir", output)
        elif action == 'copy':
            lwr_path = self._output_path(name, self.job_id, 'work_dir')['path']
            self._copy(lwr_path, output_path)

    @parseJson()
    def _output_path(self, name, job_id, output_type):
        return self._raw_execute("output_path",
                                 {"name": name,
                                  "job_id": self.job_id,
                                  "output_type": output_type})

    @retry()
    def __raw_download_output(self, name, job_id, output_type, output_path):
        output_params = {
            "name": name,
            "job_id": self.job_id,
            "output_type": output_type
        }
        self._raw_execute("download_output", output_params, output_path=output_path)

    def launch(self, command_line):
        """
        Run or queue up the execution of the supplied
        `command_line` on the remote server.

        **Parameters**

        command_line : str
            Command to execute.
        """
        launch_params = dict(command_line=command_line, job_id=self.job_id)
        submit_params = self._submit_params
        if submit_params:
            launch_params['params'] = dumps(submit_params)
        return self._raw_execute("launch", launch_params)

    def kill(self):
        """
        Cancel remote job, either removing from the queue or killing it.
        """
        return self._raw_execute("kill", {"job_id": self.job_id})

    def wait(self):
        """
        Wait for job to finish.
        """
        while True:
            complete_response = self.raw_check_complete()
            if complete_response["complete"] == "true":
                return complete_response
            sleep(1)

    @parseJson()
    def raw_check_complete(self):
        """
        Get check_complete response from the remote server.
        """
        check_complete_response = self._raw_execute("check_complete", {"job_id": self.job_id})
        return check_complete_response

    def check_complete(self, response=None):
        """
        Return boolean indicating whether the job is complete.
        """
        if response is None:
            response = self.raw_check_complete()
        return response["complete"] == "true"

    @retry()
    def get_status(self):
        check_complete_response = self.raw_check_complete()
        # Older LWR instances won't set status so use 'complete', at some
        # point drop backward compatibility.
        complete = self.check_complete(check_complete_response)
        old_status = "complete" if complete else "running"
        status = check_complete_response.get("status", old_status)
        # Bug in certains older LWR instances returned literal "status".
        if status not in ["complete", "running", "queued"]:
            status = old_status
        return status

    def clean(self):
        """
        Cleanup the remote job.
        """
        self._raw_execute("clean", {"job_id": self.job_id})

    @parseJson()
    def setup(self, tool_id=None, tool_version=None):
        """
        Setup remote LWR server to run this job.
        """
        setup_args = {"job_id": self.job_id}
        if tool_id:
            setup_args["tool_id"] = tool_id
        if tool_version:
            setup_args["tool_version"] = tool_version
        return self._raw_execute("setup", setup_args)

    def _copy(self, source, destination):
        source = os.path.abspath(source)
        destination = os.path.abspath(destination)
        if source != destination:
            shutil.copyfile(source, destination)


class InputCachingClient(Client):
    """
    Beta client that cache's staged files to prevent duplication.
    """

    def __init__(self, destination_params, job_id, job_manager_interface, client_cacher):
        super(InputCachingClient, self).__init__(destination_params, job_id, job_manager_interface)
        self.client_cacher = client_cacher

    @parseJson()
    def _upload_file(self, args, contents, input_path):
        action = self._upload_file_action(args)
        if contents:
            input_path = None
            return self._raw_execute(action, args, contents, input_path)
        else:
            event_holder = self.client_cacher.acquire_event(input_path)
            cache_required = self.cache_required(input_path)
            if cache_required:
                self.client_cacher.queue_transfer(self, input_path)
            while not event_holder.failed:
                available = self.file_available(input_path)
                if available['ready']:
                    token = available['token']
                    args["cache_token"] = token
                    return self._raw_execute(action, args)
                event_holder.event.wait(30)
            if event_holder.failed:
                raise Exception("Failed to transfer file %s" % input_path)

    @parseJson()
    def cache_required(self, path):
        return self._raw_execute("cache_required", {"path": path})

    @parseJson()
    def cache_insert(self, path):
        return self._raw_execute("cache_insert", {"path": path}, None, path)

    @parseJson()
    def file_available(self, path):
        return self._raw_execute("file_available", {"path": path})