/**
 * Owner-private opt-in to a single SQLite-backed Durable Object wake channel.
 *
 * The private ChatGPT Site's exact version manager, DO provisioning, migration
 * history and protected rollback must be verified BEFORE building with this
 * enabled. The default is absent, preserving the previously deployed binding
 * surface. Source configuration alone does not deploy or activate a namespace.
 */
export function wakeBindingConfig({enabled=false}={}) {
  if(enabled!==true)return {};
  return {
    durable_objects:{
      bindings:[{name:'RDC_WAKE_CHANNEL',class_name:'RDCWakeSignal'}],
    },
    migrations:[{
      tag:'rdc-wake-sqlite-v1',
      new_sqlite_classes:['RDCWakeSignal'],
    }],
  };
}
