|table_catalog|table_schema|table_name|column_name|ordinal_position|column_default|is_nullable|data_type|character_maximum_length|character_octet_length|numeric_precision|numeric_precision_radix|numeric_scale|datetime_precision|interval_type|interval_precision|character_set_catalog|character_set_schema|character_set_name|collation_catalog|collation_schema|collation_name|domain_catalog|domain_schema|domain_name|udt_catalog|udt_schema|udt_name|scope_catalog|scope_schema|scope_name|maximum_cardinality|dtd_identifier|is_self_referencing|is_identity|identity_generation|identity_start|identity_increment|identity_maximum|identity_minimum|identity_cycle|is_generated|generation_expression|is_updatable|column_comment|
|-------------|------------|----------|-----------|----------------|--------------|-----------|---------|------------------------|----------------------|-----------------|-----------------------|-------------|------------------|-------------|------------------|---------------------|--------------------|------------------|-----------------|----------------|--------------|--------------|-------------|-----------|-----------|----------|--------|-------------|------------|----------|-------------------|--------------|-------------------|-----------|-------------------|--------------|------------------|----------------|----------------|--------------|------------|---------------------|------------|--------------|
|noggin_db|noggin_schema|attachments|record_tip|1||NO|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||1|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|attachment_tip|2||NO|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||2|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|attachment_sequence|3||NO|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|filename|4||NO|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||4|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|file_path|5||NO|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||5|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|file_size_bytes|6||YES|bigint|||64|2|0|||||||||||||noggin_db|pg_catalog|int8|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|file_hash_md5|7||YES|character varying|32|128||||||||||||||||noggin_db|pg_catalog|varchar|||||7|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|attachment_status|8||NO|USER-DEFINED||||||||||||||||||noggin_db|noggin_schema|attachment_status_enum|||||8|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|attachment_validation_status|9||NO|USER-DEFINED||||||||||||||||||noggin_db|noggin_schema|validation_status_enum|||||9|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|validation_error_message|10||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||10|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|download_started_at|11||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||11|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|download_completed_at|12||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||12|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|download_duration_seconds|13||YES|numeric|||10|10|2|||||||||||||noggin_db|pg_catalog|numeric|||||13|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|retry_count|14|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||14|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|last_error_message|15||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||15|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|created_at|16|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||16|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|attachments|updated_at|17|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||17|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|tip_hash|1||NO|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||1|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|lookup_type|2||NO|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||2|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|resolved_value|3||NO|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|created_at|4|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||4|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|updated_at|5|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||5|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|hash_lookup|source_type|6||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tip|1||NO|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||1|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|object_type|2||NO|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||2|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|inspection_date|3||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|noggin_reference|4||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||4|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|coupling_id|5||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||5|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|inspected_by|6||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_hash|7||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||7|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle|8||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||8|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_id|9||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||9|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_hash|10||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||10|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer|11||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||11|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_id|12||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||12|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer2_hash|13||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||13|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer2|14||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||14|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer2_id|15||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||15|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer3_hash|16||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||16|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer3|17||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||17|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer3_id|18||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||18|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|job_number|19||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||19|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|run_number|20||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||20|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|driver_loader_name|21||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||21|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|department_hash|22||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||22|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|department|23||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||23|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|team_hash|24||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||24|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|team|25||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||25|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_compliance|26||YES|character varying|20|80||||||||||||||||noggin_db|pg_catalog|varchar|||||26|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|processing_status|27||NO|USER-DEFINED||||||||||||||||||noggin_db|noggin_schema|processing_status_enum|||||27|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|processing_started_at|28||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||28|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|processing_locked_by|29||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||29|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|has_unknown_hashes|30|false|YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||30|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|total_attachments|31|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||31|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|completed_attachment_count|32|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||32|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|all_attachments_complete|33|false|YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||33|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|last_error_message|34||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||34|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|retry_count|35|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||35|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|last_retry_at|36||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||36|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|next_retry_at|37||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||37|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|permanently_failed|38|false|YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||38|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|csv_imported_at|39||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||39|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_created_date|40||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||40|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_modified_date|41||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||41|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_security|42||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||42|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_type|43||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||43|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_tip|44||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||44|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_sid|45||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||45|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_branch|46||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||46|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_parent|47||YES|ARRAY||||||||||||||||||noggin_db|pg_catalog|_text|||||47|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_errors|48||YES|jsonb||||||||||||||||||noggin_db|pg_catalog|jsonb|||||48|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_meta_raw|49||YES|jsonb||||||||||||||||||noggin_db|pg_catalog|jsonb|||||49|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|api_payload_raw|50||YES|jsonb||||||||||||||||||noggin_db|pg_catalog|jsonb|||||50|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|created_at|51|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||51|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|updated_at|52|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||52|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|straps|53||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||53|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_of_straps|54||YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||54|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|chains|55||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||55|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|mass|56||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||56|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|raw_json|57||YES|jsonb||||||||||||||||||noggin_db|pg_catalog|jsonb|||||57|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|expected_inspection_id|58||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||58|NO|NO||||||NO|NEVER||YES|Inspection ID from source CSV file (e.g., LCS - 000004). Populated by SFTP downloader before API fetch.|
|noggin_db|noggin_schema|noggin_data|expected_inspection_date|59||YES|date||||||0||||||||||||noggin_db|pg_catalog|date|||||59|NO|NO||||||NO|NEVER||YES|Inspection date from source CSV file. Populated by SFTP downloader before API fetch.|
|noggin_db|noggin_schema|noggin_data|source_filename|60||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||60|NO|NO||||||NO|NEVER||YES|Original filename from SFTP server (e.g., exported-file-3a2c1734-37c7-4569-8859-2d5e17e8fe6e.csv).|
|noggin_db|noggin_schema|noggin_data|person_completing|61||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||61|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|person_involved|62||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||62|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|site_manager|63||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||63|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|persons_completing|64||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||64|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|goldstar_asset|65||YES|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||65|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|prestart_status|66||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||66|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|rego|67||YES|character varying|20|80||||||||||||||||noggin_db|pg_catalog|varchar|||||67|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|regular_driver|68||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||68|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|details_1|69||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||69|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|findings_1|70||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||70|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|summary_1|71||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||71|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|details_2|72||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||72|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|findings_2|73||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||73|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|summary_2|74||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||74|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicles|75||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||75|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|observation_date|76||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||76|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|customer_client|77||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||77|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_audit_id|78||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||78|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|driver_present_yes|79||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||79|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|driver_present_no|80||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||80|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|externally_excellent|81||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||81|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|externally_good|82||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||82|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|externally_fair|83||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||83|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|externally_unacceptable|84||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||84|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|internally_excellent|85||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||85|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|internally_good|86||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||86|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|internally_fair|87||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||87|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|internally_unacceptable|88||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||88|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|comments|89||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||89|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|revolving_beacon_yes|90||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||90|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|revolving_beacon_no|91||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||91|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|revolving_beacon_na|92||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||92|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|spare_tyre_yes|93||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||93|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|spare_tyre_no|94||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||94|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|spare_tyre_na|95||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||95|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fire_extinguisher_yes|96||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||96|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fire_extinguisher_no|97||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||97|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fire_extinguisher_na|98||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||98|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_restraint_yes|99||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||99|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_restraint_no|100||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||100|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_restraint_na|101||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||101|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_of_webbing_straps|102||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||102|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_of_chains|103||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||103|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_of_gluts|104||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||104|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|driver_comment|105||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||105|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|forklift_inspection_id|106||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||106|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|asset_type|107||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||107|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|asset_id|108||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||108|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|asset_name|109||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||109|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|hour_reading|110||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||110|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|general_comments|111||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||111|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|damage_compliant|112||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||112|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|damage_defect|113||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||113|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|damage_comments|114||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||114|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_leaks_compliant|115||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||115|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_leaks_defect|116||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||116|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_leaks_comments|117||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||117|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tyres_wheels_compliant|118||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||118|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tyres_wheels_defect|119||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||119|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tyres_wheels_comments|120||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||120|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fork_tynes_compliant|121||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||121|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fork_tynes_defect|122||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||122|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fork_tynes_comments|123||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||123|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|chains_hoses_cables_compliant|124||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||124|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|chains_hoses_cables_defect|125||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||125|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|chains_hoses_cables_comments|126||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||126|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|guards_compliant|127||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||127|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|guards_defect|128||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||128|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|guards_comments|129||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||129|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|safety_devices_compliant|130||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||130|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|safety_devices_defect|131||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||131|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|safety_devices_comments|132||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||132|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|capacity_plate_compliant|133||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||133|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|capacity_plate_defect|134||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||134|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|capacity_plate_comments|135||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||135|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_level_compliant|136||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||136|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_level_defect|137||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||137|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|fluid_level_comments|138||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||138|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lpg_compliant|139||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||139|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lpg_defect|140||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||140|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lpg_comments|141||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||141|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|radiator_fan_compliant|142||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||142|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|radiator_fan_defect|143||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||143|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|radiator_fan_comments|144||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||144|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|air_cleaner_compliant|145||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||145|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|air_cleaner_defect|146||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||146|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|air_cleaner_comments|147||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||147|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|transmission_fluid_compliant|148||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||148|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|transmission_fluid_defect|149||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||149|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|transmission_fluid_comments|150||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||150|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|audible_alarms_compliant|151||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||151|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|audible_alarms_defect|152||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||152|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|audible_alarms_comments|153||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||153|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|brakes_compliant|154||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||154|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|brakes_defect|155||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||155|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|brakes_comments|156||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||156|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|inching_pedal_compliant|157||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||157|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|inching_pedal_defect|158||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||158|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|inching_pedal_comments|159||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||159|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|steering_compliant|160||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||160|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|steering_defect|161||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||161|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|steering_comments|162||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||162|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|hydraulic_controls_compliant|163||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||163|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|hydraulic_controls_defect|164||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||164|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|hydraulic_controls_comments|165||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||165|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|attachments_compliant|166||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||166|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|attachments_defect|167||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||167|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|attachment_comments|168||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||168|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|interlock_governor_compliant|169||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||169|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|interlock_governor_defect|170||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||170|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|interlock_governor_comments|171||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||171|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|checkbox_trailer2|172||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||172|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|checkbox_trailer3|173||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||173|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|skid_plate_contact_t1|174||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||174|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|turntable_release_engaged_t1|175||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||175|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|king_pin_engaged_t1|176||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||176|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_test_performed_t1|177||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||177|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_tests_count_t1|178||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||178|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_legs_raised_t1|179||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||179|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|skid_plate_contact_t2|180||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||180|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|turntable_release_engaged_t2|181||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||181|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|king_pin_engaged_t2|182||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||182|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_test_performed_t2|183||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||183|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_tests_count_t2|184||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||184|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|ring_feeder_pin_engaged_t2|185||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||185|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_legs_raised_t2|186||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||186|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|skid_plate_contact_t3|187||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||187|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|turntable_release_engaged_t3|188||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||188|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|king_pin_engaged_t3|189||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||189|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_test_performed_t3|190||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||190|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tug_tests_count_t3|191||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||191|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|ring_feeder_pin_engaged_t3|192||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||192|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|trailer_legs_raised_t3|193||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||193|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lcs_inspection_id|194||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||194|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|goldstar_or_contractor|195||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||195|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|contractor_name|196||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||196|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_appropriate_yes|197||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||197|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_appropriate_no|198||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||198|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_appropriate_na|199||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||199|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|vehicle_appropriate_text|200||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||200|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_distributed_yes|201||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||201|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_distributed_no|202||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||202|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_distributed_na|203||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||203|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_distributed_text|204||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||204|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_sitting_yes|205||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||205|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_sitting_no|206||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||206|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_sitting_na|207||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||207|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|load_sitting_text|208||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||208|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|galas_corners_yes|209||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||209|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|galas_corners_no|210||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||210|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|galas_corners_na|211||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||211|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|galas_corners_text|212||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||212|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_appropriate_yes|213||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||213|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_appropriate_no|214||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||214|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_appropriate_na|215||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||215|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_appropriate_text|216||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||216|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|low_lashing_angle_yes|217||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||217|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|low_lashing_angle_no|218||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||218|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|low_lashing_angle_na|219||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||219|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|low_lashing_angle_text|220||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||220|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|additional_restraint_yes|221||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||221|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|additional_restraint_no|222||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||222|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|additional_restraint_na|223||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||223|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|additional_restraint_text|224||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||224|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_loose_items_yes|225||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||225|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_loose_items_no|226||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||226|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_loose_items_na|227||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||227|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_loose_items_text|228||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||228|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|headboard_height_yes|229||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||229|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|headboard_height_no|230||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||230|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|headboard_height_na|231||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||231|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|headboard_height_text|232||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||232|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|mass_dimension_yes|233||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||233|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|mass_dimension_no|234||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||234|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|mass_dimension_na|235||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||235|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|mass_dimension_text|236||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||236|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallets_condition_yes|237||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||237|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallets_condition_no|238||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||238|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallets_condition_na|239||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||239|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallets_condition_text|240||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||240|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tailgates_secured_yes|241||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||241|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tailgates_secured_no|242||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||242|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tailgates_secured_na|243||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||243|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tailgates_secured_text|244||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||244|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_anchored_yes|245||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||245|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_anchored_no|246||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||246|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_anchored_na|247||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||247|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_anchored_text|248||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||248|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_positioned_yes|249||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||249|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_positioned_no|250||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||250|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_positioned_na|251||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||251|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lashings_positioned_text|252||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||252|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_rectangular_dunnage_yes|253||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||253|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_rectangular_dunnage_no|254||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||254|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_rectangular_dunnage_na|255||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||255|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_rectangular_dunnage_text|256||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||256|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|strap_protection_yes|257||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||257|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|strap_protection_no|258||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||258|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|strap_protection_na|259||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||259|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|strap_protection_text|260||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||260|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallet_jacks_secured_yes|261||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||261|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallet_jacks_secured_no|262||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||262|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallet_jacks_secured_na|263||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||263|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|pallet_jacks_secured_text|264||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||264|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dangerous_goods_gates_yes|265||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||265|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dangerous_goods_gates_no|266||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||266|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dangerous_goods_gates_na|267||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||267|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dangerous_goods_gates_text|268||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||268|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|restraint_equipment_yes|269||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||269|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|restraint_equipment_no|270||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||270|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|restraint_equipment_na|271||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||271|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|restraint_equipment_text|272||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||272|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dunnage_aligned_yes|273||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||273|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dunnage_aligned_no|274||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||274|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dunnage_aligned_na|275||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||275|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|dunnage_aligned_text|276||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||276|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|product_protection_yes|277||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||277|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|product_protection_no|278||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||278|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|product_protection_na|279||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||279|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|product_protection_text|280||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||280|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tool_boxes_secured_yes|281||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||281|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tool_boxes_secured_no|282||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||282|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tool_boxes_secured_na|283||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||283|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|tool_boxes_secured_text|284||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||284|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|gluts|285||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||285|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|webbings|286||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||286|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|no_of_webbings|287||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||287|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|comments_actions|288||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||288|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|compliance_yes|289||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||289|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|compliance_no|290||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||290|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|non_compliance_reason|291||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||291|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|site_observation_id|292||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||292|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|observation_1_checkbox|293||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||293|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|observation_2_checkbox|294||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||294|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|details_3|295||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||295|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|findings_3|296||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||296|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|summary_3|297||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||297|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|observation_3_checkbox|298||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||298|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|details_4|299||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||299|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|findings_4|300||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||300|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|summary_4|301||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||301|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|observation_4_checkbox|302||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||302|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|lcd_inspection_id|303||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||303|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|total_load_mass_trailer1|304||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||304|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|total_load_mass_trailer2|305||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||305|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|total_load_mass_trailer3|306||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||306|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|driver|307||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||307|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|loader|308||YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||308|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|noggin_data|loader_photo_attachment|309||YES|character varying|255|1020||||||||||||||||noggin_db|pg_catalog|varchar|||||309|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|error_id|1|nextval('processing_errors_error_id_seq'::regclass)|NO|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||1|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|tip|2||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||2|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|error_timestamp|3|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|error_type|4||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||4|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|error_message|5||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||5|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|error_details|6||YES|jsonb||||||||||||||||||noggin_db|pg_catalog|jsonb|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|retry_attempt|7||YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||7|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|processing_errors|resolved|8|false|YES|boolean||||||||||||||||||noggin_db|pg_catalog|bool|||||8|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|session_id|1||NO|character varying|100|400||||||||||||||||noggin_db|pg_catalog|varchar|||||1|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|session_started_at|2|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||2|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|session_ended_at|3||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|script_version|4||YES|character varying|20|80||||||||||||||||noggin_db|pg_catalog|varchar|||||4|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|tips_processed|5|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||5|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|tips_successful|6|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|tips_failed|7|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||7|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|total_attachments_downloaded|8|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||8|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|total_file_size_mb|9|0|YES|numeric|||12|10|2|||||||||||||noggin_db|pg_catalog|numeric|||||9|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|rate_limit_429_count|10|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||10|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|total_api_calls|11|0|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||11|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|processing_duration_seconds|12||YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||12|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|data_version|13||YES|character varying|20|80||||||||||||||||noggin_db|pg_catalog|varchar|||||13|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|session_log|processing_priority|14||YES|character varying|20|80||||||||||||||||noggin_db|pg_catalog|varchar|||||14|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|unknown_hashes|tip_hash|1||NO|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||1|NO|NO||||||NO|NEVER||YES|The SHA256 hash from Noggin API|
|noggin_db|noggin_schema|unknown_hashes|lookup_type|2||NO|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||2|NO|NO||||||NO|NEVER||YES|Entity type: vehicle, trailer, team, department|
|noggin_db|noggin_schema|unknown_hashes|first_seen_at|3|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||3|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|unknown_hashes|first_seen_tip|4||YES|character varying|64|256||||||||||||||||noggin_db|pg_catalog|varchar|||||4|NO|NO||||||NO|NEVER||YES|TIP of the record where hash was first encountered|
|noggin_db|noggin_schema|unknown_hashes|first_seen_inspection_id|5||YES|character varying|50|200||||||||||||||||noggin_db|pg_catalog|varchar|||||5|NO|NO||||||NO|NEVER||YES|Inspection ID (e.g. LCD-027072) where hash was first seen|
|noggin_db|noggin_schema|unknown_hashes|last_seen_at|6|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||6|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|unknown_hashes|occurrence_count|7|1|YES|integer|||32|2|0|||||||||||||noggin_db|pg_catalog|int4|||||7|NO|NO||||||NO|NEVER||YES|Number of times this hash has been encountered|
|noggin_db|noggin_schema|unknown_hashes|resolved_at|8||YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||8|NO|NO||||||NO|NEVER||YES|When the hash was manually resolved (NULL if unresolved)|
|noggin_db|noggin_schema|unknown_hashes|resolved_value|9||YES|text||1073741824||||||||||||||||noggin_db|pg_catalog|text|||||9|NO|NO||||||NO|NEVER||YES|The resolved human-readable value|
|noggin_db|noggin_schema|unknown_hashes|created_at|10|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||10|NO|NO||||||NO|NEVER||YES||
|noggin_db|noggin_schema|unknown_hashes|updated_at|11|CURRENT_TIMESTAMP|YES|timestamp without time zone||||||6||||||||||||noggin_db|pg_catalog|timestamp|||||11|NO|NO||||||NO|NEVER||YES||
