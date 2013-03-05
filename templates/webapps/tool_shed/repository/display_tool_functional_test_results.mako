<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />
<%namespace file="/webapps/tool_shed/common/common.mako" import="*" />
<%namespace file="/webapps/tool_shed/repository/common.mako" import="*" />

<%
    from galaxy.web.framework.helpers import time_ago

    changeset_revision = repository_metadata.changeset_revision
    has_metadata = repository.metadata_revisions
    has_readme = metadata and 'readme' in metadata
    is_admin = trans.user_is_admin()
    is_new = repository.is_new( trans.app )
    is_deprecated = repository.deprecated

    can_browse_contents = trans.webapp.name == 'tool_shed' and not is_new
    can_contact_owner = trans.user and trans.user != repository.user
    can_download = not is_new and ( not is_malicious or can_push )
    can_manage = is_admin or repository.user == trans.user
    can_push = trans.app.security_agent.can_push( trans.app, trans.user, repository )
    can_rate = repository.user != trans.user
    can_review_repository = has_metadata and not is_deprecated and trans.app.security_agent.user_can_review_repositories( trans.user )
    can_upload = can_push
    can_view_change_log = trans.webapp.name == 'tool_shed' and not is_new
    if repository_metadata.tool_test_errors:
        # The tool_test_errors is mis-named (it should have been named tool_test_results) it will contain a dictionary that includes information
        # about the test environment even if all tests passed and the repository_metadata.tools_functionally_correct column is set to True.
        tool_test_errors = repository_metadata.tool_test_errors
        test_environment_dict = tool_test_errors.get( 'test_environment', None )
        test_errors = tool_test_errors.get( 'test_errors', [] )
    else:
        tool_test_errors = None
        test_environment_dict = {}
        test_errors = []

    if can_push:
        browse_label = 'Browse or delete repository tip files'
    else:
        browse_label = 'Browse repository tip files'
%>

<%!
   def inherit(context):
       if context.get('use_panels'):
           return '/webapps/tool_shed/base_panels.mako'
       else:
           return '/base.mako'
%>
<%inherit file="${inherit(context)}"/>

<br/><br/>
<ul class="manage-table-actions">
    %if is_new:
        <a class="action-button" href="${h.url_for( controller='upload', action='upload', repository_id=trans.security.encode_id( repository.id ) )}">Upload files to repository</a>
    %else:
        <li><a class="action-button" id="repository-${repository.id}-popup" class="menubutton">Repository Actions</a></li>
        <div popupmenu="repository-${repository.id}-popup">
            %if can_review_repository:
                %if reviewed_by_user:
                    <a class="action-button" href="${h.url_for( controller='repository_review', action='edit_review', id=review_id )}">Manage my review of this revision</a>
                %else:
                    <a class="action-button" href="${h.url_for( controller='repository_review', action='create_review', id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision )}">Add a review to this revision</a>
                %endif
            %endif
            %if can_manage:
                <a class="action-button" href="${h.url_for( controller='repository', action='manage_repository', id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision )}">Manage repository</a>
            %else:
                <a class="action-button" href="${h.url_for( controller='repository', action='view_repository', id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision )}">View repository</a>
            %endif
            %if can_upload:
                <a class="action-button" href="${h.url_for( controller='upload', action='upload', repository_id=trans.security.encode_id( repository.id ) )}">Upload files to repository</a>
            %endif
            %if can_view_change_log:
                <a class="action-button" href="${h.url_for( controller='repository', action='view_changelog', id=trans.app.security.encode_id( repository.id ) )}">View change log</a>
            %endif
            %if can_browse_contents:
                <a class="action-button" href="${h.url_for( controller='repository', action='browse_repository', id=trans.app.security.encode_id( repository.id ) )}">${browse_label}</a>
            %endif
            %if can_contact_owner:
                <a class="action-button" href="${h.url_for( controller='repository', action='contact_owner', id=trans.security.encode_id( repository.id ) )}">Contact repository owner</a>
            %endif
            %if can_download:
                <a class="action-button" href="${h.url_for( controller='repository', action='download', repository_id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision, file_type='gz' )}">Download as a .tar.gz file</a>
                <a class="action-button" href="${h.url_for( controller='repository', action='download', repository_id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision, file_type='bz2' )}">Download as a .tar.bz2 file</a>
                <a class="action-button" href="${h.url_for( controller='repository', action='download', repository_id=trans.app.security.encode_id( repository.id ), changeset_revision=changeset_revision, file_type='zip' )}">Download as a zip file</a>
            %endif
        </div>
    %endif
</ul>

%if message:
    ${render_msg( message, status )}
%endif

<div class="toolForm">
    <div class="toolFormTitle">Repository revision</div>
    <div class="toolFormBody">
        <div class="form-row">
            <label>Revision:</label>
            %if can_view_change_log:
                <a href="${h.url_for( controller='repository', action='view_changelog', id=trans.app.security.encode_id( repository.id ) )}">${revision_label}</a>
            %else:
                ${revision_label}
            %endif
        </div>
    </div>
</div>
<p/>
%if can_download:
    <div class="toolForm">
        <div class="toolFormTitle">Repository '${repository.name}'</div>
        <div class="toolFormBody">
            <div class="form-row">
                <label>Clone this repository:</label>
                ${render_clone_str( repository )}
            </div>
        </div>
    </div>
%else:
    <b>Repository name:</b><br/>
    ${repository.name}
%endif
%if tool_test_errors:
    <p/>
    <div class="toolForm">
        <div class="toolFormTitle">Tool functional test results</div>
        <div class="toolFormBody">
            <div class="form-row">
                <label>Time tested:</label>
                ${time_ago( repository_metadata.time_last_tested ) | h}
            </div>
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Test environment</td></tr>
                </table>
            </div>
            <div class="form-row">
                <label>Architecture:</label>
                ${test_environment_dict.get( 'architecture', 'unknown' ) | h}
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <label>Python version:</label>
                ${test_environment_dict.get( 'python_version', 'unknown' ) | h}
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <label>Operating system:</label>
                ${test_environment_dict.get( 'system', 'unknown' ) | h}
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <table width="100%">
                    <tr bgcolor="#D8D8D8" width="100%"><td><b>Test results</td></tr>
                </table>
            </div>
            <div class="form-row">
                <table class="grid">
                    %for test_results_dict in test_errors:
                        <tr>
                            <td bgcolor="#FFFFCC"><b>Test id</b></td>
                            <td bgcolor="#FFFFCC">${test_results_dict.get( 'test_id', 'unknown' )}</td>
                        </tr>
                        %if repository_metadata.tools_functionally_correct:
                            <tr>
                                <td><b>Stdout</b></td>
                                <td>${test_results_dict.get( 'stdout', '' )}</td>
                            </tr>
                        %else:
                            <tr>
                                <td><b>Stderr</b></td>
                                <td>${test_results_dict.get( 'stderr', '' )}</td>
                            </tr>
                            <tr>
                                <td><b>Traceback</b></td>
                                <td>${test_results_dict.get( 'traceback', '' )}</td>
                            </tr>
                        %endif
                    %endfor
                </table>
                <div style="clear: both"></div>
            </div>
        </div>
    </div>
%endif