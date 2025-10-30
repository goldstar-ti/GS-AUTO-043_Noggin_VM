# 1. Global UNKNOWN constant
Add to common/__init__.py:
```python
# Global constants
UNKNOWN_TEXT = "UNKNOWN"
```

# Then import everywhere:
``` python
from common import UNKNOWN_TEXT 
```
# 2. Database schema changes
``` sql
-- Add missing fields
ALTER TABLE noggin_schema.noggin_data 
ADD COLUMN straps boolean NULL,
ADD COLUMN no_of_straps integer NULL,
ADD COLUMN chains boolean NULL,
ADD COLUMN mass varchar(50) NULL,
ADD COLUMN raw_json jsonb NULL;
```
No defaults. Keep as NULL in database.

# 3. NULL in DB + display UNKNOWN
When inserting/updating noggin_data, pass Python None for missing fields. 
PostgreSQL stores as NULL.

When displaying (in text file or queries), use COALESCE:

In save_formatted_payload_text_file():
``` python
straps_value = response_data.get('straps')
if straps_value is not None:
    f.write(f"Straps:                {straps_value}\n\n")
    no_of_straps = response_data.get('noOfStraps', UNKNOWN_TEXT)
    f.write(f"Number of Straps:      {no_of_straps}\n\n")

chains_value = response_data.get('chains')
if chains_value is not None:
    f.write(f"Chains:                {chains_value}\n\n")

mass_value = response_data.get('mass', UNKNOWN_TEXT)
f.write(f"Mass:                  {mass_value}\n\n")
```
For SQL queries retrieving data:
``` sql
SELECT 
    COALESCE(straps::text, 'UNKNOWN') as straps_display,
    COALESCE(no_of_straps::text, 'UNKNOWN') as no_of_straps_display,
    COALESCE(chains::text, 'UNKNOWN') as chains_display,
    COALESCE(mass, 'UNKNOWN') as mass_display
FROM noggin_data;
```
# 4. Auto-update lookup_type logic
In hash_manager.py, add this method:
``` python
def update_lookup_type_if_unknown(self, tip_hash: str, context_key: str) -> None:
    """
    Update lookup_type from unknown to context key if still unknown
    
    Args:
        tip_hash: Hash value
        context_key: Key from JSON (team, vehicle, whichDepartmentDoesTheLoadBelongTo, trailer)
    """
    normalised_key = 'department' if context_key == 'whichDepartmentDoesTheLoadBelongTo' else context_key
    
    try:
        self.db_manager.execute_update(
            """
            UPDATE hash_lookup
            SET lookup_type = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE tip_hash = %s
              AND lookup_type = 'unknown'
            """,
            (normalised_key, tip_hash)
        )
        
        if (tip_hash, 'unknown') in self._cache:
            value = self._cache.pop((tip_hash, 'unknown'))
            self._cache[(tip_hash, normalised_key)] = value
            logger.debug(f"Updated lookup_type: {tip_hash[:16]}... from unknown to {normalised_key}")
            
    except Exception as e:
        logger.debug(f"Could not update lookup_type for {tip_hash}: {e}")
```        
In noggin_processor.py, modify insert_noggin_data_record() to call this after each lookup:
``` python
vehicle_hash: Optional[str] = response_data.get('vehicle')
vehicle: Optional[str] = None
if vehicle_hash:
    vehicle = hash_manager.lookup_hash('vehicle', vehicle_hash, tip_value, lcd_inspection_id)
    hash_manager.update_lookup_type_if_unknown(vehicle_hash, 'vehicle')

trailer_hash: Optional[str] = response_data.get('trailer')
trailer: Optional[str] = None
if trailer_hash:
    trailer = hash_manager.lookup_hash('trailer', trailer_hash, tip_value, lcd_inspection_id)
    hash_manager.update_lookup_type_if_unknown(trailer_hash, 'trailer')

# Same for trailer2, trailer3...

department_hash: Optional[str] = response_data.get('whichDepartmentDoesTheLoadBelongTo')
department: Optional[str] = None
if department_hash:
    department = hash_manager.lookup_hash('department', department_hash, tip_value, lcd_inspection_id)
    hash_manager.update_lookup_type_if_unknown(department_hash, 'whichDepartmentDoesTheLoadBelongTo')

team_hash: Optional[str] = response_data.get('team')
team: Optional[str] = None
if team_hash:
    team = hash_manager.lookup_hash('team', team_hash, tip_value, lcd_inspection_id)
    hash_manager.update_lookup_type_if_unknown(team_hash, 'team')
```
# 5. Store raw JSON
In insert_noggin_data_record(), add raw_json to the INSERT:
``` python
db_manager.execute_update(
    """
    INSERT INTO noggin_data (
        tip, object_type, inspection_date, lcd_inspection_id, coupling_id,
        inspected_by, vehicle_hash, vehicle, vehicle_id,
        trailer_hash, trailer, trailer_id,
        trailer2_hash, trailer2, trailer2_id,
        trailer3_hash, trailer3, trailer3_id,
        job_number, run_number, driver_loader_name,
        department_hash, department, team_hash, team,
        load_compliance, processing_status, has_unknown_hashes,
        total_attachments, csv_imported_at,
        straps, no_of_straps, chains, mass,
        api_meta_created_date, api_meta_modified_date,
        api_meta_security, api_meta_type, api_meta_tip,
        api_meta_sid, api_meta_branch, api_meta_parent,
        api_meta_errors, api_meta_raw, api_payload_raw, raw_json
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s,
        %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s
    )
    ON CONFLICT (tip) DO UPDATE SET
        # ... existing fields ...
        straps = EXCLUDED.straps,
        no_of_straps = EXCLUDED.no_of_straps,
        chains = EXCLUDED.chains,
        mass = EXCLUDED.mass,
        raw_json = EXCLUDED.raw_json,
        updated_at = CURRENT_TIMESTAMP
    """,
    (
        # ... existing parameters ...
        response_data.get('straps'),
        response_data.get('noOfStraps'),
        response_data.get('chains'),
        response_data.get('mass'),
        # ... existing parameters ...
        json.dumps(response_data)  # raw_json at end
    )
)
```

# Questions:
1. Does update_lookup_type_if_unknown() only update hash_lookup table, or should it also update hash_lookup_unknown table?
2. Should the raw_json field store the entire response_data, or just specific sections?
3. Do you want logging when lookup_type gets updated from unknown?
RetryClaude can make mistakes. Please double-check responses.