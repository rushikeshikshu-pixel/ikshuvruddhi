CREATE TABLE `mills` (
	`owner_id` text PRIMARY KEY NOT NULL,
	`name` text NOT NULL,
	`location` text NOT NULL,
	`season` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `plots` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`plot_no` text NOT NULL,
	`village` text NOT NULL,
	`variety` text NOT NULL,
	`cane_type` text NOT NULL,
	`area` real NOT NULL,
	`planting_date` text NOT NULL,
	`acquisition_date` text,
	`cloud` real,
	`ndvi` real,
	`harvest_date` text,
	`priority` text DEFAULT 'Review' NOT NULL,
	`created_at` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `plots_owner_number` ON `plots` (`owner_id`,`plot_no`);--> statement-breakpoint
CREATE TABLE `samples` (
	`id` text PRIMARY KEY NOT NULL,
	`owner_id` text NOT NULL,
	`plot_id` text NOT NULL,
	`sample_date` text NOT NULL,
	`pol` real NOT NULL,
	`brix` real NOT NULL,
	`recovery` real,
	`created_at` text NOT NULL
);
