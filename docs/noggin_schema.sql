-- noggin_schema.attachments definition

-- Drop table

-- DROP TABLE noggin_schema.attachments;

CREATE TABLE noggin_schema.attachments (
	record_tip varchar(64) NOT NULL,
	attachment_tip varchar(64) NOT NULL,
	attachment_sequence int4 NOT NULL,
	filename varchar(255) NOT NULL,
	file_path text NOT NULL,
	file_size_bytes int8 NULL,
	file_hash_md5 varchar(32) NULL,
	attachment_status noggin_schema."attachment_status_enum" NOT NULL,
	attachment_validation_status noggin_schema."validation_status_enum" NOT NULL,
	validation_error_message text NULL,
	download_started_at timestamp NULL,
	download_completed_at timestamp NULL,
	download_duration_seconds numeric(10, 2) NULL,
	retry_count int4 DEFAULT 0 NULL,
	last_error_message text NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	CONSTRAINT attachments_pkey PRIMARY KEY (record_tip, attachment_tip)
);
CREATE INDEX idx_attachments_record_tip ON noggin_schema.attachments USING btree (record_tip);
CREATE INDEX idx_attachments_status ON noggin_schema.attachments USING btree (attachment_status);

-- Table Triggers

create trigger trg_update_attachment_completion after
insert
    or
delete
    or
update
    on
    noggin_schema.attachments for each row execute function noggin_schema.update_attachment_completion();
create trigger trg_attachments_updated_at before
update
    on
    noggin_schema.attachments for each row execute function noggin_schema.update_modified_timestamp();


-- noggin_schema.attachments foreign keys

ALTER TABLE noggin_schema.attachments ADD CONSTRAINT attachments_record_tip_fkey FOREIGN KEY (record_tip) REFERENCES noggin_schema.noggin_data(tip) ON DELETE CASCADE;

-- noggin_schema.hash_lookup definition

-- Drop table

-- DROP TABLE noggin_schema.hash_lookup;

CREATE TABLE noggin_schema.hash_lookup (
	tip_hash varchar(64) NOT NULL,
	lookup_type varchar(50) NOT NULL,
	resolved_value text NOT NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	source_type varchar(50) NULL,
	CONSTRAINT hash_lookup_pkey PRIMARY KEY (tip_hash)
);
CREATE INDEX idx_hash_lookup_lookup_type ON noggin_schema.hash_lookup USING btree (lookup_type);
CREATE INDEX idx_hash_lookup_resolved_value ON noggin_schema.hash_lookup USING btree (resolved_value);
CREATE INDEX idx_hash_lookup_source_type ON noggin_schema.hash_lookup USING btree (source_type);

-- Table Triggers

create trigger trg_hash_lookup_updated_at before
update
    on
    noggin_schema.hash_lookup for each row execute function noggin_schema.update_modified_timestamp();

	-- noggin_schema.noggin_data definition

-- Drop table

-- DROP TABLE noggin_schema.noggin_data;

CREATE TABLE noggin_schema.noggin_data (
	tip varchar(64) NOT NULL,
	object_type varchar(50) NOT NULL,
	inspection_date timestamp NULL,
	lcd_inspection_id varchar(50) NULL,
	coupling_id varchar(50) NULL,
	inspected_by varchar(100) NULL,
	vehicle_hash varchar(64) NULL,
	vehicle varchar(100) NULL,
	vehicle_id varchar(50) NULL,
	trailer_hash varchar(64) NULL,
	trailer varchar(100) NULL,
	trailer_id varchar(50) NULL,
	trailer2_hash varchar(64) NULL,
	trailer2 varchar(100) NULL,
	trailer2_id varchar(50) NULL,
	trailer3_hash varchar(64) NULL,
	trailer3 varchar(100) NULL,
	trailer3_id varchar(50) NULL,
	job_number varchar(50) NULL,
	run_number varchar(50) NULL,
	driver_loader_name varchar(100) NULL,
	department_hash varchar(64) NULL,
	department varchar(100) NULL,
	team_hash varchar(64) NULL,
	team varchar(100) NULL,
	load_compliance varchar(20) NULL,
	processing_status noggin_schema."processing_status_enum" NOT NULL,
	processing_started_at timestamp NULL,
	processing_locked_by varchar(100) NULL,
	has_unknown_hashes bool DEFAULT false NULL,
	total_attachments int4 DEFAULT 0 NULL,
	completed_attachment_count int4 DEFAULT 0 NULL,
	all_attachments_complete bool DEFAULT false NULL,
	last_error_message text NULL,
	retry_count int4 DEFAULT 0 NULL,
	last_retry_at timestamp NULL,
	next_retry_at timestamp NULL,
	permanently_failed bool DEFAULT false NULL,
	csv_imported_at timestamp NULL,
	api_meta_created_date timestamp NULL,
	api_meta_modified_date timestamp NULL,
	api_meta_security varchar(64) NULL,
	api_meta_type varchar(64) NULL,
	api_meta_tip varchar(64) NULL,
	api_meta_sid varchar(64) NULL,
	api_meta_branch varchar(100) NULL,
	api_meta_parent _text NULL,
	api_meta_errors jsonb NULL,
	api_meta_raw jsonb NULL,
	api_payload_raw jsonb NULL,
	created_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	updated_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	straps bool NULL,
	no_of_straps int4 NULL,
	chains bool NULL,
	mass varchar(50) NULL,
	raw_json jsonb NULL,
	expected_inspection_id varchar(50) NULL,
	expected_inspection_date date NULL,
	source_filename varchar(255) NULL,
	CONSTRAINT noggin_data_pkey PRIMARY KEY (tip)
);
CREATE INDEX idx_noggin_data_api_meta_parent ON noggin_schema.noggin_data USING gin (api_meta_parent);
CREATE INDEX idx_noggin_data_department ON noggin_schema.noggin_data USING btree (department);
CREATE INDEX idx_noggin_data_driver_loader_name ON noggin_schema.noggin_data USING btree (driver_loader_name);
CREATE INDEX idx_noggin_data_expected_inspection_id ON noggin_schema.noggin_data USING btree (expected_inspection_id) WHERE (expected_inspection_id IS NOT NULL);
CREATE INDEX idx_noggin_data_has_unknown_hashes ON noggin_schema.noggin_data USING btree (has_unknown_hashes);
CREATE INDEX idx_noggin_data_inspected_by ON noggin_schema.noggin_data USING btree (inspected_by);
CREATE INDEX idx_noggin_data_inspection_date ON noggin_schema.noggin_data USING btree (inspection_date);
CREATE INDEX idx_noggin_data_lcd_inspection_id ON noggin_schema.noggin_data USING btree (lcd_inspection_id);
CREATE INDEX idx_noggin_data_next_retry_at ON noggin_schema.noggin_data USING btree (next_retry_at);
CREATE INDEX idx_noggin_data_object_type ON noggin_schema.noggin_data USING btree (object_type);
CREATE INDEX idx_noggin_data_pending_by_type ON noggin_schema.noggin_data USING btree (object_type, processing_status) WHERE (processing_status = 'pending'::noggin_schema.processing_status_enum);
CREATE INDEX idx_noggin_data_processing_started_at ON noggin_schema.noggin_data USING btree (processing_started_at);
CREATE INDEX idx_noggin_data_processing_status ON noggin_schema.noggin_data USING btree (processing_status);
CREATE INDEX idx_noggin_data_source_filename ON noggin_schema.noggin_data USING btree (source_filename) WHERE (source_filename IS NOT NULL);
CREATE INDEX idx_noggin_data_vehicle ON noggin_schema.noggin_data USING btree (vehicle);

-- Table Triggers

create trigger trg_noggin_data_updated_at before
update
    on
    noggin_schema.noggin_data for each row execute function noggin_schema.update_modified_timestamp();

	-- noggin_schema.processing_errors definition

-- Drop table

-- DROP TABLE noggin_schema.processing_errors;

CREATE TABLE noggin_schema.processing_errors (
	error_id serial4 NOT NULL,
	tip varchar(64) NULL,
	error_timestamp timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	error_type varchar(50) NULL,
	error_message text NULL,
	error_details jsonb NULL,
	retry_attempt int4 NULL,
	resolved bool DEFAULT false NULL,
	CONSTRAINT processing_errors_pkey PRIMARY KEY (error_id)
);
CREATE INDEX idx_processing_errors_timestamp ON noggin_schema.processing_errors USING btree (error_timestamp);
CREATE INDEX idx_processing_errors_tip ON noggin_schema.processing_errors USING btree (tip);


-- noggin_schema.processing_errors foreign keys

ALTER TABLE noggin_schema.processing_errors ADD CONSTRAINT processing_errors_tip_fkey FOREIGN KEY (tip) REFERENCES noggin_schema.noggin_data(tip) ON DELETE CASCADE;

-- noggin_schema.session_log definition

-- Drop table

-- DROP TABLE noggin_schema.session_log;

CREATE TABLE noggin_schema.session_log (
	session_id varchar(100) NOT NULL,
	session_started_at timestamp DEFAULT CURRENT_TIMESTAMP NULL,
	session_ended_at timestamp NULL,
	script_version varchar(20) NULL,
	tips_processed int4 DEFAULT 0 NULL,
	tips_successful int4 DEFAULT 0 NULL,
	tips_failed int4 DEFAULT 0 NULL,
	total_attachments_downloaded int4 DEFAULT 0 NULL,
	total_file_size_mb numeric(12, 2) DEFAULT 0 NULL,
	rate_limit_429_count int4 DEFAULT 0 NULL,
	total_api_calls int4 DEFAULT 0 NULL,
	processing_duration_seconds int4 NULL,
	data_version varchar(20) NULL,
	processing_priority varchar(20) NULL,
	CONSTRAINT session_log_pkey PRIMARY KEY (session_id)
);
