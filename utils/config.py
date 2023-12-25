import logging
import os


class Config:

    def __init__(self, project_name: str):
        self.root = os.path.abspath(os.curdir)
        self.project_name: str = project_name
        self.input = self.create_folder("input")
        self.output = self.create_folder("output")
        self.figure = self.create_folder("output/figure")
        self.task_id = None
        self.task_output = None
        # self.config_logging()

    @staticmethod
    def create_folder(path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        return path

    def set_task_id(self, task_id: int) -> "Config":
        self.task_id = task_id
        self.task_output = os.path.join(self.output, f"task_{task_id}")
        if not os.path.exists(self.task_output):
            os.makedirs(self.task_output)
        return self

    @staticmethod
    def config_logging():
        logging.getLogger("pyomo.core").setLevel(logging.ERROR)

    def make_copy(self) -> "Config":
        rk = self.__class__(self.project_name)
        for k, v in self.__dict__.items():
            rk.__dict__[k] = v
        return rk

