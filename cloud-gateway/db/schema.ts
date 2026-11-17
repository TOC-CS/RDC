import { sqliteTable, text, integer, index, uniqueIndex } from "drizzle-orm/sqlite-core";

export const gatewayOwner = sqliteTable("gateway_owner", {
  id: integer("id").primaryKey(),
  principal: text("principal").notNull(),
  createdMs: integer("created_ms").notNull(),
});

export const gatewayDevice = sqliteTable("gateway_device", {
  id: text("id").primaryKey(),
  lastSeenMs: integer("last_seen_ms").notNull(),
});

export const gatewayOperations = sqliteTable("gateway_operations", {
  id: text("id").primaryKey(),
  principal: text("principal").notNull(),
  deviceId: text("device_id").notNull(),
  requestKey: text("request_key").notNull(),
  tool: text("tool").notNull(),
  requestJson: text("request_json"),
  requestSha256: text("request_sha256").notNull(),
  requestSize: integer("request_size").notNull(),
  mutating: integer("mutating").notNull(),
  state: text("state").notNull(),
  claimId: text("claim_id"),
  createdMs: integer("created_ms").notNull(),
  expiresMs: integer("expires_ms").notNull(),
  claimedMs: integer("claimed_ms"),
  completedMs: integer("completed_ms"),
  resultKey: text("result_key"),
  resultInlineJson: text("result_inline_json"),
  resultSha256: text("result_sha256"),
  resultSize: integer("result_size").notNull().default(0),
  resultExpiresMs: integer("result_expires_ms"),
}, table => [
  uniqueIndex("gateway_operation_key").on(table.principal, table.deviceId, table.requestKey),
  index("gateway_operation_queue").on(table.deviceId, table.state, table.createdMs),
  index("gateway_operation_retention").on(table.resultExpiresMs),
]);
