from uuid import UUID

from pydantic import BaseModel


class Favorite(BaseModel):
    user_id: UUID
    item_id: UUID
    item_type: str