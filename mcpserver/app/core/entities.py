from pydantic import BaseModel


class Student(BaseModel):
    id: str
    califications: dict[str, float]


class Course(BaseModel):
    id: str
    title: str
    description: str
    students: list[Student] = []

    # ... otros campos relevantes
