from fastapi import APIRouter, HTTPException, status

from api.app.deps import AnyRole, CurrentUser, DbSession, FarmerOnly
from api.app.models import Farm, User
from api.app.models.trade import Wallet
from api.app.schemas.auth import UserOut
from api.app.schemas.user import FarmCreate, FarmOut, WalletOut
from api.app.services.escrow import get_wallet

router = APIRouter(tags=["users"])


@router.patch("/me", response_model=UserOut)
def update_me(patch: dict, user: CurrentUser, db: DbSession):
    allowed = {"full_name", "locale", "phone"}
    for key, value in patch.items():
        if key not in allowed:
            raise HTTPException(status_code=400, detail=f"Field {key} is not editable")
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@router.get("/me/wallet", response_model=WalletOut)
def my_wallet(user: CurrentUser, db: DbSession):
    return get_wallet(db, user.id)


@router.get("/farms", response_model=list[FarmOut])
def list_my_farms(user: CurrentUser, db: DbSession):
    return db.query(Farm).filter(Farm.owner_id == user.id).all()


@router.post("/farms", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(body: FarmCreate, user: FarmerOnly, db: DbSession):
    farm = Farm(owner_id=user.id, **body.model_dump())
    db.add(farm)
    db.commit()
    db.refresh(farm)
    return farm


@router.get("/farms/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: int, user: AnyRole, db: DbSession):
    farm = db.get(Farm, farm_id)
    if not farm:
        raise HTTPException(status_code=404, detail="Farm not found")
    return farm
