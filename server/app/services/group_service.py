import logging
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional, Any
from app.models.group import Group, GroupMember
from app.models.friend import Friend
from app.schemas.group import GroupCreate, GroupUpdate
from app.services.memo.constants import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


class GroupService:
    DEFAULT_USER_AVATAR = "default_avatar.svg"

    @staticmethod
    def _get_user_avatar(db: Session) -> str:
        """
        Get user avatar from system settings.
        Returns DEFAULT_USER_AVATAR if not set.
        """
        from app.models.system_setting import SystemSetting
        setting = db.query(SystemSetting).filter_by(group_name="user", key="avatar").first()
        if setting and setting.value:
            return setting.value
        return GroupService.DEFAULT_USER_AVATAR

    @staticmethod
    def _populate_group_members(db: Session, group: Group) -> None:
        """
        Populate member names, avatars and count for a group.
        Modifies the group object in place.
        """
        group.member_count = len(group.members)
        
        # Batch fetch friend info
        friend_ids = [m.member_id for m in group.members if m.member_type == "friend"]
        friends_map = {}
        if friend_ids:
            friends_map = {str(f.id): f for f in db.query(Friend).filter(Friend.id.in_(friend_ids)).all()}
        
        # Get user avatar once
        user_avatar = GroupService._get_user_avatar(db)
        
        for m in group.members:
            if m.member_type == "friend":
                f = friends_map.get(m.member_id)
                if f:
                    m.name = f.name
                    m.avatar = f.avatar
                else:
                    m.name = "Unknown"
                    m.avatar = None
            else:
                m.name = "我"
                m.avatar = user_avatar

    @staticmethod
    def _populate_last_message(db: Session, group: Group) -> None:
        """
        Populate last message preview for a group.
        """
        from app.models.group import GroupMessage
        from sqlalchemy import desc
        
        last_msg = db.query(GroupMessage).filter(
            GroupMessage.group_id == group.id
        ).order_by(desc(GroupMessage.create_time)).first()
        
        if last_msg:
            # For groups, we use _strip_message_tags if it was available.
            # FriendService has _strip_message_tags.
            from app.services.friend_service import _strip_message_tags
            group.last_message = _strip_message_tags(last_msg.content)
            group.last_message_time = last_msg.create_time
            
            if last_msg.sender_type == "user":
                group.last_message_sender_name = "我"
            else:
                # Find friend name in members (members should be populated already)
                sender = next((m for m in group.members if m.member_id == last_msg.sender_id and m.member_type == "friend"), None)
                if sender and hasattr(sender, 'name'):
                    group.last_message_sender_name = sender.name
                else:
                    group.last_message_sender_name = "其它"
        else:
            group.last_message = None
            group.last_message_time = None
            group.last_message_sender_name = None

    @staticmethod
    def get_user_groups(db: Session, user_id: str = DEFAULT_USER_ID) -> List[Group]:
        """
        Get all groups the user belongs to with member count and populated members.
        """
        groups = db.query(Group).join(GroupMember).filter(
            and_(
                GroupMember.member_id == user_id,
                GroupMember.member_type == "user"
            )
        ).all()
        
        for g in groups:
            GroupService._populate_group_members(db, g)
            GroupService._populate_last_message(db, g)
        
        # Sort groups by last message time descending
        groups.sort(key=lambda x: (x.last_message_time or x.update_time or x.create_time), reverse=True)
        
        return groups

    @staticmethod
    def create_group(db: Session, group_in: GroupCreate, owner_id: str = DEFAULT_USER_ID) -> Group:
        """
        Create a new group and add initial members.
        """
        try:
            # 1. Create group
            db_group = Group(
                name=group_in.name,
                avatar=group_in.avatar,
                description=group_in.description,
                owner_id=owner_id
            )
            db.add(db_group)
            db.flush()  # Get group ID

            # 2. Add owner as a member
            owner_member = GroupMember(
                group_id=db_group.id,
                member_id=owner_id,
                member_type="user"
            )
            db.add(owner_member)

            # 3. Add initial members (AI friends)
            for member_id in group_in.member_ids:
                # Avoid adding owner again if they are in the list
                if member_id == owner_id:
                    continue
                
                member = GroupMember(
                    group_id=db_group.id,
                    member_id=member_id,
                    member_type="friend"
                )
                db.add(member)

            db.commit()
            db.refresh(db_group)
            
            # Populate members and count for response
            GroupService._populate_group_members(db, db_group)

            logger.info(f"Created group '{db_group.name}' (id={db_group.id}) with {len(group_in.member_ids)} initial members")
            return db_group
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create group: {e}")
            raise

    @staticmethod
    def get_group(db: Session, group_id: int) -> Optional[Group]:
        """
        Get group by ID with members populated with name and avatar.
        """
        db_group = db.query(Group).filter(Group.id == group_id).first()
        if not db_group:
            return None
        
        GroupService._populate_group_members(db, db_group)
        GroupService._populate_last_message(db, db_group)
        return db_group

    @staticmethod
    def is_member(db: Session, group_id: int, member_id: str, member_type: str = "user") -> bool:
        """
        Check if a user/friend is a member of a group.
        """
        return db.query(GroupMember).filter(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.member_id == member_id,
                GroupMember.member_type == member_type
            )
        ).first() is not None

    @staticmethod
    def add_members(db: Session, group_id: int, member_ids: List[str], requester_id: str = DEFAULT_USER_ID) -> bool:
        """
        Add new members to a group.
        Only members can invite others (simplified, requirement doesn't specify only owner can invite).
        """
        # Check if requester is a member
        if not GroupService.is_member(db, group_id, requester_id):
            logger.warning(f"User {requester_id} attempted to invite members to group {group_id} but is not a member")
            return False

        added_count = 0
        for member_id in member_ids:
            # Check if already a member
            if not GroupService.is_member(db, group_id, member_id, "friend"):
                member = GroupMember(
                    group_id=group_id,
                    member_id=member_id,
                    member_type="friend"
                )
                db.add(member)
                added_count += 1
        
        db.commit()
        logger.info(f"Added {added_count} members to group {group_id}")
        return True

    @staticmethod
    def update_group(db: Session, group_id: int, group_in: GroupUpdate, requester_id: str = DEFAULT_USER_ID) -> Optional[Group]:
        """
        Update group settings. Only owner can update.
        """
        db_group = GroupService.get_group(db, group_id)
        if not db_group:
            return None
        
        if db_group.owner_id != requester_id:
            logger.warning(f"User {requester_id} attempted to update group {group_id} but is not owner")
            return None

        update_data = group_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_group, field, value)

        db.commit()
        db.refresh(db_group)
        logger.info(f"Updated group {group_id} settings: {list(update_data.keys())}")
        return db_group

    @staticmethod
    def exit_group(db: Session, group_id: int, user_id: str = DEFAULT_USER_ID) -> bool:
        """
        Let user exit a group.
        If owner exits, group is dissolved.
        """
        db_group = GroupService.get_group(db, group_id)
        if not db_group:
            return False
        
        # If owner exits, delete the whole group (dissolve)
        # In this single-human sandbox, if the user exits, the group is gone
        if db_group.owner_id == user_id:
            db.delete(db_group)
            db.commit()
            logger.info(f"Owner {user_id} exited group {group_id} - dissolved group")
            return True
        
        member = db.query(GroupMember).filter(
                GroupMember.group_id == group_id,
                GroupMember.member_id == user_id,
                GroupMember.member_type == "user"
        ).first()

        if not member:
            return False

        db.delete(member)
        db.commit()
        logger.info(f"User {user_id} exited group {group_id}")
        return True

    @staticmethod
    def remove_member(db: Session, group_id: int, member_id: str, requester_id: str = DEFAULT_USER_ID) -> bool:
        """
        Remove a member. Only owner can remove. Owner cannot remove themselves.
        """
        db_group = GroupService.get_group(db, group_id)
        if not db_group:
            return False
        
        if db_group.owner_id != requester_id:
            logger.warning(f"User {requester_id} attempted to remove member from group {group_id} but is not owner")
            return False
        
        # Prevent owner from removing themselves
        if member_id == requester_id:
            logger.warning(f"Owner {requester_id} attempted to remove themselves from group {group_id}")
            return False

        member = db.query(GroupMember).filter(
            and_(
                GroupMember.group_id == group_id,
                GroupMember.member_id == member_id
            )
        ).first()

        if not member:
            return False

        db.delete(member)
        db.commit()
        logger.info(f"Removed member {member_id} from group {group_id}")
        return True


group_service = GroupService()
