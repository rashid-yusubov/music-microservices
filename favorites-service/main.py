from uuid import UUID

from fastapi import FastAPI, Depends, HTTPException, status

from security.auth import get_current_user
from services.favorite_service import favorite_service
from clients.external_client import ExternalServiceError


app = FastAPI(title="Favorites Service")


@app.put(
    "/api/v1/favorites/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def add_track(
    track_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    try:
        favorite_service.add_track(user_id, track_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ExternalServiceError as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.delete(
    "/api/v1/favorites/tracks/{track_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_track(
    track_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    favorite_service.remove_track(user_id, track_id)


@app.put(
    "/api/v1/favorites/playlists/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def add_playlist(
    playlist_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    try:
        favorite_service.add_playlist(user_id, playlist_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except ExternalServiceError as error:
        raise HTTPException(status_code=503, detail=str(error))


@app.delete(
    "/api/v1/favorites/playlists/{playlist_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def remove_playlist(
    playlist_id: UUID,
    user_id: UUID = Depends(get_current_user)
):
    favorite_service.remove_playlist(user_id, playlist_id)