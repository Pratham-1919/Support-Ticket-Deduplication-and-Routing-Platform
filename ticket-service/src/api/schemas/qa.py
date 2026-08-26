from pydantic import BaseModel, Field
 
 
class QuestionRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Question about historical support tickets",
    )