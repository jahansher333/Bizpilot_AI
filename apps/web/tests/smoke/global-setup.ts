import { assertLocalSmokeDatabase, resetSmokeDatabase } from './smoke-db';

export default function globalSetup(): void {
  resetSmokeDatabase(assertLocalSmokeDatabase(process.env.SMOKE_DATABASE_URL));
}
