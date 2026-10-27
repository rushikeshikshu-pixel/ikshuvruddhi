CREATE TABLE `boundaries` (
	`plot_id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`geometry` text NOT NULL,
	`hash` text NOT NULL,
	`updated_at` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `satellite_observations` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`plot_id` text NOT NULL,
	`date` text NOT NULL,
	`sensor` text NOT NULL,
	`boundary_hash` text NOT NULL,
	`result` text NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `satellite_observation_unique` ON `satellite_observations` (`owner_id`,`plot_id`,`date`,`sensor`,`boundary_hash`);--> statement-breakpoint
CREATE TABLE `satellite_requests` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`created_at` integer NOT NULL
);
--> statement-breakpoint
CREATE INDEX `satellite_request_time` ON `satellite_requests` (`created_at`);--> statement-breakpoint
CREATE INDEX `satellite_request_owner` ON `satellite_requests` (`owner_id`,`created_at`);