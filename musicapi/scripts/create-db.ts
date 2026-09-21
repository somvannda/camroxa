import { Client } from "pg";

const DB_NAME = "sunoapi";
const ADMIN_URL = "postgres://postgres:postgres@localhost:5432/postgres";

async function main() {
  const client = new Client({ connectionString: ADMIN_URL });
  await client.connect();
  const exists = await client.query("SELECT 1 FROM pg_database WHERE datname = $1", [DB_NAME]);
  if (exists.rowCount === 0) {
    await client.query(`CREATE DATABASE ${DB_NAME}`);
    console.log(`Created database "${DB_NAME}".`);
  } else {
    console.log(`Database "${DB_NAME}" already exists.`);
  }
  await client.end();
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
