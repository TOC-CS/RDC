CREATE TABLE `gateway_device` (
	`id` text PRIMARY KEY NOT NULL,
	`last_seen_ms` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `gateway_operations` (
	`id` text PRIMARY KEY NOT NULL,
	`principal` text NOT NULL,
	`device_id` text NOT NULL,
	`request_key` text NOT NULL,
	`tool` text NOT NULL,
	`request_json` text,
	`request_sha256` text NOT NULL,
	`request_size` integer NOT NULL,
	`mutating` integer NOT NULL,
	`state` text NOT NULL,
	`claim_id` text,
	`created_ms` integer NOT NULL,
	`expires_ms` integer NOT NULL,
	`claimed_ms` integer,
	`completed_ms` integer,
	`result_key` text,
	`result_sha256` text,
	`result_size` integer DEFAULT 0 NOT NULL,
	`result_expires_ms` integer
);
--> statement-breakpoint
CREATE UNIQUE INDEX `gateway_operation_key` ON `gateway_operations` (`principal`,`device_id`,`request_key`);--> statement-breakpoint
CREATE INDEX `gateway_operation_queue` ON `gateway_operations` (`device_id`,`state`,`created_ms`);--> statement-breakpoint
CREATE INDEX `gateway_operation_retention` ON `gateway_operations` (`result_expires_ms`);--> statement-breakpoint
CREATE TABLE `gateway_owner` (
	`id` integer PRIMARY KEY NOT NULL,
	`principal` text NOT NULL,
	`created_ms` integer NOT NULL
);
