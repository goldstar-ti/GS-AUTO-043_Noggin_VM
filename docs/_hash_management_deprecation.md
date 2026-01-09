# Hash Management Refactoring - Deprecation Notes

**Date:** January 2026  
**Author:** Craig / Claude  
**Git Reference:** Check previous commits for original implementations

---

## Overview

The hash management system has been refactored to use authoritative weekly exports from Noggin rather than tracking unknown hashes during processing. This simplification removes significant complexity while improving data accuracy.

---

## Architecture Change

### Previous Approach
- Hashes encountered during processing that weren't in `hash_lookup` were logged to `hash_lookup_unknown` table
- Manual resolution workflow: export unknowns → fill in values → re-import
- Type detection was heuristic-based (pattern matching on resolved values)

### New Approach  
- Weekly sync from Noggin's authoritative asset and site exports
- Drop and recreate `hash_lookup` table contents
- Types determined from source data (`assetType`, `siteType`)
- No unknown hash tracking - if a hash isn't found, it will appear in next week's sync

---

## Removed from hash_manager.py

### Functions Removed

| Function | Purpose | Why Removed |
|----------|---------|-------------|
| `_log_unknown_hash()` | Wrote unknown hashes to `unknown_hashes.log` file | Unknown hash tracking deprecated |
| `migrate_lookup_table_from_csv()` | One-time migration from legacy `lookup_table.csv` | Migration complete, legacy file retired |
| `_detect_lookup_type()` | Heuristic detection of type from resolved value patterns | Types now come from authoritative source |
| `resolve_unknown_hash()` | Manually resolve a single unknown hash | No more unknown hash workflow |
| `get_unknown_hashes()` | List unresolved or resolved unknown hashes | No more unknown hash tracking |
| `export_unknown_hashes()` | Export unknowns to CSV for manual resolution | No more unknown hash workflow |
| `auto_resolve_unknown_hashes()` | Bulk resolve unknowns that now exist in hash_lookup | No more unknown hash tracking |
| `update_lookup_type_if_unknown()` | Update 'unknown' type based on context during processing | Types are authoritative from source |
| `import_hashes_from_csv()` | Import from TIP/VALUE format CSV | Replaced by new sync from Noggin exports |

### Modified Functions

| Function | Change |
|----------|--------|
| `lookup_hash()` | Simplified - no longer inserts into `hash_lookup_unknown` on miss, just returns None |
| `__init__()` | Removed `log_path` attribute (was only used for unknown hash logging) |

### Retained Functions

| Function | Purpose |
|----------|---------|
| `_load_cache()` | Load hash lookups into memory for performance |
| `lookup_hash()` | Core lookup function used by processors |
| `search_hash()` | Search by resolved value (useful for reporting) |
| `get_hash_statistics()` | Statistics for dashboard display |

---

## Removed from manage_hashes.py

### Commands Removed

| Command | Purpose | Why Removed |
|---------|---------|-------------|
| `import` | Import hashes from TIP/VALUE CSV | Replaced by `hash_lookup_sync.py` |
| `export-unknown` | Export unknown hashes for resolution | Unknown hash workflow deprecated |
| `list` | List known hashes by type | Can be done via `hash_lookup_sync.py --stats` |

### Commands Retained

| Command | Purpose |
|---------|---------|
| `stats` | Display hash statistics (refactored) |
| `search` | Search for hash or name (refactored) |

### Note on manage_hashes.py

The original `manage_hashes.py` had several issues:
1. Referenced `entity_hashes` table which doesn't exist (should be `hash_lookup`)
2. Had orphaned function `update_lookup_type_if_unknown()` outside any class (lines 382-410)
3. GUI file picker functionality was Windows-centric

The refactored version focuses on the two useful operations: stats and search.

---

## Database Changes

### Table Removed

```sql
DROP TABLE noggin_schema.hash_lookup_unknown;
```

This table tracked:
- `tip_hash` - The unknown hash value
- `lookup_type` - What type of entity it was
- `first_encountered` - When we first saw it
- `resolved_at` - When/if it was resolved
- `resolved_value` - The resolved value (after manual resolution)

No longer needed because:
1. Weekly authoritative sync means unknowns are temporary
2. If an entity exists in Noggin, it will appear in next export
3. If it doesn't exist, it's a data quality issue to address at source

### Table Modified: hash_lookup

**New column added:**
```sql
source_type VARCHAR(50)  -- Stores assetType or siteType from Noggin
```

**Primary key changed:**
- Old: Composite key on `(tip_hash, lookup_type)`
- New: Single column key on `tip_hash`

Rationale: A Noggin hash uniquely identifies ONE entity. The same hash cannot be both a vehicle and a trailer.

---

## File Removed

### unknown_hashes.log

This file in the log directory tracked unknown hash encounters with:
- Timestamp
- Lookup type
- Hash value
- LCD Inspection ID
- TIP value

No longer generated because unknown hashes are not tracked.

---

## New Scripts

### hash_lookup_sync.py

Replaces the import functionality with:
- Reads Noggin export CSVs (asset and site)
- Determines `lookup_type` from `assetType`/`siteType`
- Populates `source_type` column with original Noggin type
- Drop and recreate approach for guaranteed consistency
- SFTP download capability for automated operation

### Usage

```bash
# Manual sync from local files
python hash_lookup_sync.py --asset-file /path/to/asset.csv --site-file /path/to/site.csv

# Automated sync from SFTP
python hash_lookup_sync.py --sftp

# Show statistics only
python hash_lookup_sync.py --stats
```

---

## Migration Checklist

- [x] Add `source_type` column to `hash_lookup`
- [x] Create index on `source_type`
- [x] Change primary key to `tip_hash` only
- [x] Drop `hash_lookup_unknown` table
- [x] Convert PPK to PEM for SFTP
- [x] Add `[sftp]` section to `base_config.ini`
- [x] Deploy `hash_lookup_sync.py`
- [x] Deploy updated `hash_manager.py`
- [x] Delete or archive `unknown_hashes.log`
- [x] Schedule weekly cron job for sync
- [ ] Test end-to-end with real Noggin exports
- [ ] Monitor first few processing runs for any lookup misses

---

## Rollback

If issues arise, the previous versions can be restored from git:

```bash
git checkout <commit-hash> -- common/hash_manager.py
git checkout <commit-hash> -- manage_hashes.py
```

The `hash_lookup_unknown` table would need to be recreated:

```sql
CREATE TABLE noggin_schema.hash_lookup_unknown (
    unknown_id SERIAL PRIMARY KEY,
    tip_hash VARCHAR(64) NOT NULL,
    lookup_type VARCHAR(50) NOT NULL,
    first_encountered TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolved_value TEXT,
    UNIQUE(tip_hash, lookup_type)
);
```