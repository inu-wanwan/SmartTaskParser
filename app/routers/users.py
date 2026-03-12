from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.request import UserRegisterRequest, LinearSetupRequest, UserConfigRequest, LLMSetupRequest
from app.models.response import UserConfigResponse
from app.services.user_service import UserService
from app.models.user import User

router = APIRouter()

def get_user_service(request: Request) -> UserService:
	"""
	FastAPI の Depends で UserService を注入するための関数。
	"""
	return request.app.state.user_service

@router.post("/users/me")
def register_user(req: UserRegisterRequest, service: UserService = Depends(get_user_service)) -> User:
	user = service.get_user_by_line_user_id(req.line_user_id)
	if not user:
		user = service.register_user(line_user_id=req.line_user_id)
	return user

@router.get("/users/me")
def get_user_config(req: UserConfigRequest, service: UserService = Depends(get_user_service)) -> UserConfigResponse:
	user = service.get_user_by_line_user_id(line_user_id=req.line_user_id)
	if not user:
		raise HTTPException(status_code=404, detail="User not found")
	
	is_linear_connected = bool(user.linear_api_key)
	is_llm_connected = bool(user.llm_api_key)

	return UserConfigResponse(
		line_user_id=user.line_user_id,
		is_linear_connected=is_linear_connected,
		is_llm_connected=is_llm_connected,
	)

@router.put("/users/linear-setup")
def setup_linear_integration(req: LinearSetupRequest, service: UserService = Depends(get_user_service)) -> User:
	try:
		user = service.get_user_by_line_user_id(req.line_user_id)
		if not user:
			raise HTTPException(status_code=404, detail="User not found")
		
		service.setup_linear_integration(
			user_id=user.id,
			raw_api_key=req.linear_api_key,
		)

		user = service.get_user_by_line_user_id(req.line_user_id)
		return user
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))
	
@router.put("/users/llm-setup")
def setup_llm_integration(req: LLMSetupRequest, service: UserService = Depends(get_user_service)) -> User:
	try:
		user = service.get_user_by_line_user_id(req.line_user_id)
		if not user:
			raise HTTPException(status_code=404, detail="User not found")
		
		service.setup_llm_integration(
			user_id=user.id,
			raw_api_key=req.llm_api_key,
		)

		user = service.get_user_by_line_user_id(req.line_user_id)
		return user
	except ValueError as e:
		raise HTTPException(status_code=400, detail=str(e))