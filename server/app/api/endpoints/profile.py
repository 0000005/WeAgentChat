from fastapi import APIRouter, HTTPException, Path, Body
from app.services.memo.bridge import MemoService, MemoServiceException
from app.services.memo.constants import DEFAULT_USER_ID, DEFAULT_SPACE_ID
from app.schemas.memory import (
    ProfileCreate, ProfileUpdate, ConfigUpdate, BatchDeleteRequest, StatusResponse, CreateProfileResponse
)
from app.vendor.memobase_server.models.response import UserProfilesData, ProfileConfigData, UserEventGistsData

router = APIRouter()

# Flag to avoid redundant initialization checks
_INITIALIZED = False

async def ensure_defaults():
    """
    Ensure the default user and space exist in the memory system.
    Cached after the first successful call during the application's runtime.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return
    try:
        await MemoService.ensure_user(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
        _INITIALIZED = True
    except MemoServiceException as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize memory system: {str(e)}")

@router.get(
    "/config", 
    response_model=ProfileConfigData,
    summary="获取资料配置",
    description="获取当前空间的个人资料分类定义 (YAML 格式)。"
)
async def get_profile_config():
    await ensure_defaults()
    try:
        return await MemoService.get_profile_config(DEFAULT_SPACE_ID)
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/config", 
    response_model=StatusResponse,
    summary="更新资料配置",
    description="更新当前空间的个人资料分类定义。"
)
async def update_profile_config(config_data: ConfigUpdate):
    await ensure_defaults()
    try:
        await MemoService.update_profile_config(DEFAULT_SPACE_ID, config_data.profile_config)
        return StatusResponse()
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/profiles", 
    response_model=UserProfilesData,
    summary="获取资料列表",
    description="获取默认用户在当前空间下的所有个人资料条目。"
)
async def get_profiles():
    await ensure_defaults()
    try:
        return await MemoService.get_user_profiles(DEFAULT_USER_ID, DEFAULT_SPACE_ID)
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post(
    "/profiles", 
    response_model=CreateProfileResponse,
    summary="新增资料条目",
    description="手动为默认用户添加一条新的个人资料。"
)
async def create_profile(profile: ProfileCreate):
    await ensure_defaults()
    try:
        # SDK expects lists for bulk operations; we wrap the single item here.
        res = await MemoService.add_user_profiles(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            contents=[profile.content],
            attributes=[profile.attributes.model_dump()]
        )
        return CreateProfileResponse(ids=[str(id) for id in res.ids])
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.put(
    "/profiles/{profile_id}", 
    response_model=StatusResponse,
    summary="更新资料条目",
    description="更新指定的个人资料条目内容或分类。"
)
async def update_profile(
    profile_id: str = Path(..., description="要更新的资料条目 ID"),
    profile: ProfileUpdate = Body(...)
):
    await ensure_defaults()
    try:
        attributes = [profile.attributes.model_dump() if profile.attributes else None]
        await MemoService.update_user_profiles(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            profile_ids=[profile_id],
            contents=[profile.content],
            attributes=attributes
        )
        return StatusResponse()
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/profiles", 
    response_model=StatusResponse,
    summary="批量删除资料",
    description="根据 ID 列表批量删除个人资料条目。"
)
async def delete_profiles(request: BatchDeleteRequest):
    await ensure_defaults()
    try:
        await MemoService.delete_user_profiles(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            profile_ids=request.profile_ids
        )
        return StatusResponse()
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete(
    "/profiles/{profile_id}", 
    response_model=StatusResponse,
    summary="删除单个资料",
    description="根据 ID 删除指定的个人资料条目。"
)
async def delete_single_profile(
    profile_id: str = Path(..., description="要删除的资料条目 ID")
):
    await ensure_defaults()
    try:
        await MemoService.delete_user_profiles(
            user_id=DEFAULT_USER_ID,
            space_id=DEFAULT_SPACE_ID,
            profile_ids=[profile_id]
        )
        return StatusResponse()
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get(
    "/events_gists", 
    response_model=UserEventGistsData,
    summary="获取好友记忆列表",
    description="获取指定好友的事件摘要列表（Gists）。"
)
async def get_friend_event_gists(friend_id: int, limit: int = 50):
    await ensure_defaults()
    try:
        return await MemoService.filter_friend_event_gists(
            user_id=DEFAULT_USER_ID, 
            space_id=DEFAULT_SPACE_ID, 
            friend_id=friend_id,
            topk=limit
        )
    except MemoServiceException as e:
        raise HTTPException(status_code=400, detail=str(e))
