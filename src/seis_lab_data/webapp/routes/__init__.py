from .auth import (
    auth_callback,
    login,
    logout,
)
from .base import (
    home,
    set_language,
    profile,
    protected,
)
from .projects import (
    add_create_project_form_link,
    add_create_survey_mission_form_link,
    get_project_creation_form,
    ProjectCollectionEndpoint,
    ProjectDetailEndpoint,
    remove_create_project_form_link,
    remove_create_survey_mission_form_link,
)
from .surveymissions import (
    get_survey_mission_creation_form,
    SurveyMissionCollectionEndpoint,
    SurveyMissionDetailEndpoint,
)
from .surveyrelatedrecords import (
    get_survey_related_record_creation_form,
    SurveyRelatedRecordCollectionEndpoint,
    SurveyRelatedRecordDetailEndpoint,
)

__ALL__ = [
    add_create_project_form_link,
    add_create_survey_mission_form_link,
    auth_callback,
    get_project_creation_form,
    get_survey_mission_creation_form,
    get_survey_related_record_creation_form,
    home,
    login,
    logout,
    ProjectCollectionEndpoint,
    ProjectDetailEndpoint,
    profile,
    protected,
    remove_create_project_form_link,
    remove_create_survey_mission_form_link,
    set_language,
    SurveyMissionCollectionEndpoint,
    SurveyMissionDetailEndpoint,
    SurveyRelatedRecordCollectionEndpoint,
    SurveyRelatedRecordDetailEndpoint,
]
