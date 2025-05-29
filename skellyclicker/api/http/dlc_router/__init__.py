import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)

dlc_router = APIRouter(
    prefix="/dlc",
    tags=["dlc"],
    responses={404: {"description": "Not found"}},
)