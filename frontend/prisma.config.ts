import "dotenv/config";
import { defineConfig } from "prisma/config";

// Append sslmode=require for the Prisma CLI (migrate/generate).
// The app runtime uses a pg.Pool with ssl:{rejectUnauthorized:false} instead
// (see src/lib/prisma.ts) because pg v8 treats sslmode=require as verify-full.
const cliUrl = process.env.DATABASE_URL
  ? process.env.DATABASE_URL.includes("?")
    ? `${process.env.DATABASE_URL}&sslmode=require`
    : `${process.env.DATABASE_URL}?sslmode=require`
  : undefined;

export default defineConfig({
  schema: "prisma/schema.prisma",
  migrations: {
    path: "prisma/migrations",
  },
  ...(cliUrl && {
    datasource: {
      url: cliUrl,
    },
  }),
});
