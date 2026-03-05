import os

from src.models.behavior.main import gen_household_profiles
from src.models.behavior.main import gen_person_profiles
from src.plotters.behavior.person_activity_share import person_activity_share
from src.utils.config import Config
from src.utils.db import prepare_project_run


def run_flex_behavior_model(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    prepare_project_run(config)
    gen_person_profiles(config)
    gen_household_profiles(config)


def run_flex_behavior_plotter(project_name: str):
    config = Config(project_name=project_name, project_path=os.path.dirname(__file__))
    person_activity_share(config, person_types=[1, 2, 3, 4], day_types=[1, 2])


if __name__ == "__main__":
    run_flex_behavior_model("test_behavior")
    # run_flex_behavior_plotter("test_behavior")
