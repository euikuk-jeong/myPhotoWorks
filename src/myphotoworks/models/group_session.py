"""GroupSession — group membership, adoption state and undo (no GUI dependencies)."""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from myphotoworks.core.explain import photo_facts
from myphotoworks.core.ranking import reason_label, recommend
from myphotoworks.core.scoring import ALGORITHM_VERSION
from myphotoworks.models.photo_item import PhotoItem

TAG_REVIEWED = "추천 채택"
TAG_EDITED = "수정됨"
TAG_TODO = "미확인"


@dataclass
class Group:
    id: int
    photos: list[PhotoItem]

    @property
    def is_single(self) -> bool:
        return len(self.photos) == 1


class GroupSession:
    """Owns the grouping of one photo list.

    Every mutating operation records a snapshot, so one user action == one undo entry
    and undoing it never touches unrelated groups.
    """

    def __init__(
        self, photos: list[PhotoItem], groups: list[list[int]], sensitivity: float = 1.0
    ) -> None:
        self._photos = photos
        self._sensitivity = sensitivity
        self._session_id = uuid.uuid4().hex
        self._order: list[int] = []
        self._members: dict[int, list[PhotoItem]] = {}
        self._next_id = 0
        self._dirty: set[int] = set()
        self._reviewed: set[int] = set()
        self._undo: list[tuple] = []
        self._added: set[int] = set()  # photos added after grouping (not analysed)
        for idxs in groups:
            gid = self._new_id()
            self._order.append(gid)
            self._members[gid] = [photos[i] for i in idxs]
            for i in idxs:
                photos[i].group_id = gid
        self.rescore(sensitivity)

    # ---- queries ---------------------------------------------------------

    def groups(self) -> list[Group]:
        return [Group(gid, list(self._members[gid])) for gid in self._order]

    def group(self, gid: int) -> Group:
        return Group(gid, list(self._members[gid]))

    def photos_flat(self) -> list[PhotoItem]:
        return list(self._photos)

    def group_count(self) -> int:
        return len(self._order)

    def single_count(self) -> int:
        return sum(1 for gid in self._order if len(self._members[gid]) == 1)

    def adopted_count(self) -> int:
        return sum(1 for p in self._photos if p.is_adopted)

    def reviewed_count(self) -> int:
        return len(self._reviewed & set(self._order))

    def visible_photos(self, adopted_only: bool) -> list[PhotoItem]:
        out = [p for gid in self._order for p in self._members[gid]]
        return [p for p in out if p.is_adopted] if adopted_only else out

    def tag(self, gid: int) -> str:
        if gid in self._dirty:
            return TAG_EDITED
        return TAG_REVIEWED if gid in self._reviewed else TAG_TODO

    @property
    def can_undo(self) -> bool:
        return bool(self._undo)

    @property
    def session_id(self) -> str:
        """Identifies this grouping run (stays the same through every edit); the selection log
        keeps one file per session."""
        return self._session_id

    @property
    def sensitivity(self) -> float:
        """Deadband multiplier the recommendations were made with (normal = 1.0)."""
        return self._sensitivity

    def to_label_dict(self, root: Path | None = None, source: str = "user",
                      photo_info=None) -> dict:
        """Snapshot of the user's decisions as an evaluation label (schema 1).

        ``photo_info`` (developer export only): ``photo -> dict``, added as ``photos`` next to
        ``files`` (same order), together with the group's ``number``, the "그룹 N" of the review
        window.

        ``reviewed``: the user opened or edited the group. Untouched groups only mirror the
        recommendation and must not be counted as labels. ``edited``: the user's pick differs
        from the recommendation, the strictest kind of label. Single-photo groups carry no
        choice and are skipped. File names are relative to ``root`` (default: the common
        parent folder); photos that cannot be expressed relative to it, or all photos when
        there is no common folder (e.g. different drives), use their own path so names never
        collide.
        """
        if root is None:
            parents = [os.fspath(p.source_path.parent) for p in self._photos]
            try:
                root = Path(os.path.commonpath(parents)) if parents else Path(".")
            except ValueError:  # different drives / mixed absolute and relative paths
                root = Path("")

        def rel(p: PhotoItem) -> str:
            try:
                return p.source_path.relative_to(root).as_posix()
            except ValueError:
                return p.source_path.as_posix()

        groups = []
        for number, gid in enumerate(self._order, start=1):
            members = self._members[gid]
            if len(members) < 2:
                continue
            picked = [rel(p) for p in members if p.is_adopted]
            recommended = next((rel(p) for p in members if p.is_recommended), None)
            reviewed = self.tag(gid) != TAG_TODO
            entry = {
                "id": gid,
                "files": [rel(p) for p in members],
                "picked": picked,
                "recommended": recommended,
                "reviewed": reviewed,
                "edited": reviewed and picked != [recommended],
            }
            if photo_info is not None:      # developer export only; the selection log stays lean
                entry["number"] = number
                entry["photos"] = [{"file": rel(p), **photo_info(p)} for p in members]
            groups.append(entry)
        return {
            "schema": 1,
            "source": source,
            "algorithm": ALGORITHM_VERSION,
            "sensitivity": self._sensitivity,
            "root": os.fspath(root),
            "groups": groups,
        }

    # ---- scoring ---------------------------------------------------------

    def rescore(self, sensitivity: float) -> None:
        """Recompute recommendations from cached scores (no decoding).

        Untouched groups follow the new recommendation; groups the user edited keep their
        adoption state and only get updated recommendation badges.
        """
        self._sensitivity = sensitivity
        for gid in self._order:
            self._refresh_recommendations(gid)
            if gid not in self._dirty:
                for p in self._members[gid]:
                    # photos that could not be analysed stay adopted so they are never dropped
                    p.is_adopted = p.is_recommended if p.scores is not None else True

    # ---- undo plumbing ---------------------------------------------------

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def _snapshot(self) -> tuple:
        return (
            list(self._order),
            {gid: list(m) for gid, m in self._members.items()},
            {id(p): (p.group_id, p.is_adopted) for p in self._photos},
            set(self._dirty),
        )

    def _push(self) -> None:
        self._undo.append(self._snapshot())

    def undo(self) -> bool:
        if not self._undo:
            return False
        order, members, states, dirty = self._undo.pop()
        self._order, self._members, self._dirty = order, members, dirty
        for p in self._photos:
            p.group_id, p.is_adopted = states[id(p)]
        for gid in self._order:
            self._refresh_recommendations(gid)
        return True

    def added_count(self) -> int:
        """Photos added after the last grouping run (they sit alone until regrouped)."""
        return sum(1 for p in self._photos if id(p) in self._added)

    def add_photos(self, added: list[PhotoItem]) -> None:
        """Append new photos as single, adopted groups; they are not scored or compared."""
        for p in added:
            gid = self._new_id()
            self._order.append(gid)
            self._members[gid] = [p]
            p.group_id, p.scores = gid, None
            p.is_recommended, p.is_adopted, p.reason, p.facts = False, True, "", ()
            self._photos.append(p)
            self._added.add(id(p))
        self._undo.clear()  # snapshots would not know these photos

    def remove_photos(self, removed: list[PhotoItem]) -> None:
        """Drop photos; groups that lose every member disappear, others keep their state."""
        gone = {id(p) for p in removed}
        self._photos = [p for p in self._photos if id(p) not in gone]
        self._added -= gone
        for gid in list(self._order):
            kept = [p for p in self._members[gid] if id(p) not in gone]
            if kept:
                self._members[gid] = kept
            else:
                del self._members[gid]
                self._order.remove(gid)
                self._dirty.discard(gid)
                self._reviewed.discard(gid)
        self._undo.clear()
        self.rescore(self._sensitivity)

    def mark_reviewed(self, gid: int) -> None:
        self._reviewed.add(gid)

    # ---- adoption --------------------------------------------------------

    def set_adopted(self, photo: PhotoItem, value: bool) -> None:
        if photo.is_adopted == value:
            return
        self._push()
        photo.is_adopted = value
        self._dirty.add(photo.group_id)

    def adopt_all(self, gid: int) -> None:
        self._set_group(gid, lambda p: True)

    def clear_all(self, gid: int) -> None:
        self._set_group(gid, lambda p: False)

    def adopt_recommended(self, gid: int) -> None:
        self._set_group(gid, lambda p: p.is_recommended)

    def _set_group(self, gid: int, rule) -> None:
        members = self._members[gid]
        if all(p.is_adopted == rule(p) for p in members):
            return
        self._push()
        for p in members:
            p.is_adopted = rule(p)
        self._dirty.add(gid)

    # ---- group editing ---------------------------------------------------

    def move_photo(self, photo: PhotoItem, dst_gid: int) -> None:
        src = photo.group_id
        if src == dst_gid or dst_gid not in self._members:
            return
        self._push()
        self._move(photo, src, dst_gid)

    def detach_photo(self, photo: PhotoItem) -> int | None:
        """Split ``photo`` off into its own new group placed right after its old one."""
        src = photo.group_id
        if len(self._members[src]) <= 1:
            return None
        self._push()
        gid = self._new_id()
        self._order.insert(self._order.index(src) + 1, gid)
        self._members[gid] = []
        self._move(photo, src, gid)
        return gid

    def split_from(self, photo: PhotoItem) -> int | None:
        """Move ``photo`` and every photo after it into a new group right after the old one."""
        src = photo.group_id
        members = self._members[src]
        k = members.index(photo)
        if k == 0:
            return None
        self._push()
        gid = self._new_id()
        self._order.insert(self._order.index(src) + 1, gid)
        self._members[gid] = []
        for p in list(members[k:]):
            self._move(p, src, gid)
        return gid

    def merge(self, keep_gid: int, absorb_gid: int) -> None:
        if keep_gid == absorb_gid or absorb_gid not in self._members:
            return
        self._push()
        for p in list(self._members[absorb_gid]):
            self._move(p, absorb_gid, keep_gid)
        # The merged group starts over: only its new recommendation is adopted, and it follows
        # the recommendation again (e.g. on sensitivity changes) until the user edits it.
        for p in self._members[keep_gid]:
            p.is_adopted = p.is_recommended if p.scores is not None else True
        self._dirty.discard(keep_gid)

    def _move(self, photo: PhotoItem, src: int, dst: int) -> None:
        self._members[src].remove(photo)
        self._members[dst].append(photo)
        photo.group_id = dst
        self._dirty.update((src, dst))
        if not self._members[src]:
            del self._members[src]
            self._order.remove(src)
            self._dirty.discard(src)
        self._refresh_recommendations(dst)
        if src in self._members:
            self._refresh_recommendations(src)

    def _refresh_recommendations(self, gid: int) -> None:
        """Update badges/reasons for an edited group without touching adoption."""
        scored = [p for p in self._members[gid] if p.scores is not None]
        if not scored:
            return
        table = [p.scores for p in scored]
        rec = recommend(table, self._sensitivity)
        for k, p in enumerate(scored):
            p.is_recommended = k == rec.index
            p.facts = photo_facts(table, k)
            parts = [reason_label(rec, len(table))] if k == rec.index else []
            p.reason = " · ".join(parts + list(p.facts))
