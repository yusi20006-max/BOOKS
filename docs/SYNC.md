# Sync contract

## Book sync envelope

A book sync change may carry the core book fields plus these extended sections:

- reading: status, current_page, progress, started_at, finished_at
- personal: rating, note, quote, favorite
- organization: tags, shelves

Omitted sections are left unchanged on update, which preserves compatibility with older clients.

## Sync ownership matrix

| Data | Sync status |
|---|---|
| Core book metadata | Synced |
| Reading status/progress/dates | Synced |
| Personal rating/note/quote/favorite | Synced |
| Tags and shelves | Synced |
| Reading sessions | Local-only for now |
| Reading goals | Local-only for now |
| Notes/quotes collections | Local-only for now |
| Physical copies | Local-only for now |
| Loans | Local-only for now |
| Digital annotations | Local-only for now |
| Audiobooks/player state | Local-only for now |

Local-only data is intentionally not included in the current sync envelope and is not silently claimed to be replicated.


## Change identity and transactions

Change IDs include a short content digest in addition to entity, entity ID, and version. This prevents two distinct payloads at the same version from colliding while replaying the same change remains idempotent.

Applying a change uses one SQLite transaction for deduplication, book/extended-state writes, and the changelog entry. If any part fails, the whole change is rolled back.

Deleting a missing book is accepted but returns applied=false and is recorded so the same change can be replayed safely.
