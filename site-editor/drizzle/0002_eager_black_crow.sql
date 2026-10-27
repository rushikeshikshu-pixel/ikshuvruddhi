CREATE TABLE `satellite_register` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`snapshot_id` text NOT NULL,
	`plot_no` text NOT NULL,
	`status` text NOT NULL,
	`complete` integer NOT NULL,
	`source_timestamp` text NOT NULL,
	`data_json` text NOT NULL,
	`is_current` integer DEFAULT 0 NOT NULL,
	`imported_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `satellite_register_snapshot_plot` ON `satellite_register` (`owner_id`,`snapshot_id`,`plot_no`);--> statement-breakpoint
CREATE INDEX `satellite_register_current_status` ON `satellite_register` (`owner_id`,`is_current`,`status`,`plot_no`);