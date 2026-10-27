// Intentionally empty by default.
// Add Drizzle tables here when the site actually needs a database.
// See examples/d1/db/schema.ts for an opt-in example.
import { sqliteTable, text, real, integer, uniqueIndex, index } from "drizzle-orm/sqlite-core";
export const mills = sqliteTable("mills", { ownerId:text("owner_id").primaryKey(), name:text("name").notNull(), location:text("location").notNull(), season:text("season").notNull() });
export const plots = sqliteTable("plots", { id:text("id").primaryKey(), ownerId:text("owner_id").notNull(), plotNo:text("plot_no").notNull(), village:text("village").notNull(), variety:text("variety").notNull(), caneType:text("cane_type").notNull(), area:real("area").notNull(), plantingDate:text("planting_date").notNull(), acquisitionDate:text("acquisition_date"), cloud:real("cloud"), ndvi:real("ndvi"), harvestDate:text("harvest_date"), priority:text("priority").notNull().default("Review"), createdAt:text("created_at").notNull() }, t=>[uniqueIndex("plots_owner_number").on(t.ownerId,t.plotNo)]);
export const samples = sqliteTable("samples", { id:text("id").primaryKey(), ownerId:text("owner_id").notNull(), plotId:text("plot_id").notNull(), sampleDate:text("sample_date").notNull(), pol:real("pol").notNull(), brix:real("brix").notNull(), recovery:real("recovery"), createdAt:text("created_at").notNull() });
export const boundaries = sqliteTable('boundaries',{plotId:text('plot_id').primaryKey(),ownerId:text('owner_id').notNull(),geometry:text('geometry').notNull(),hash:text('hash').notNull(),updatedAt:text('updated_at').notNull()});
export const satelliteObservations = sqliteTable('satellite_observations',{id:text('id').primaryKey(),ownerId:text('owner_id').notNull(),plotId:text('plot_id').notNull(),date:text('date').notNull(),sensor:text('sensor').notNull(),boundaryHash:text('boundary_hash').notNull(),result:text('result').notNull(),createdAt:text('created_at').notNull()},t=>[uniqueIndex('satellite_observation_unique').on(t.ownerId,t.plotId,t.date,t.sensor,t.boundaryHash)]);
export const satelliteRequests = sqliteTable('satellite_requests',{id:text('id').primaryKey(),ownerId:text('owner_id').notNull(),createdAt:integer('created_at').notNull()},t=>[index('satellite_request_time').on(t.createdAt),index('satellite_request_owner').on(t.ownerId,t.createdAt)]);
export const satelliteRegister = sqliteTable('satellite_register', {
  id: text('id').primaryKey(),
  ownerId: text('owner_id').notNull(),
  snapshotId: text('snapshot_id').notNull(),
  plotNo: text('plot_no').notNull(),
  status: text('status').notNull(),
  complete: integer('complete').notNull(),
  sourceTimestamp: text('source_timestamp').notNull(),
  dataJson: text('data_json').notNull(),
  isCurrent: integer('is_current').notNull().default(0),
  importedAt: text('imported_at').notNull(),
}, t => [uniqueIndex('satellite_register_snapshot_plot').on(t.ownerId, t.snapshotId, t.plotNo), index('satellite_register_current_status').on(t.ownerId, t.isCurrent, t.status, t.plotNo)]);
