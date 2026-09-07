from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.modules.auth.schemas import CurrentUser
from app.modules.instructor import service as instructor_service
from app.modules.instructor.schemas import BecomeInstructorRequest, InstructorResponse

router = APIRouter(prefix="/instructor", tags=["Instructor"])


@router.post("/become", response_model=InstructorResponse, status_code=status.HTTP_201_CREATED)
async def become_instructor(
    payload: BecomeInstructorRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InstructorResponse:
    instructor = await instructor_service.become_instructor(
        db,
        user_id=current_user.id,
        payload=payload,
    )
    return InstructorResponse(message="You are now an instructor", data=instructor)
