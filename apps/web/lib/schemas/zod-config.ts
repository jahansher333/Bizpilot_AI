import { z } from "zod";

// Zod's JIT probes `new Function("")`. Under the app's CSP (no 'unsafe-eval') the probe is
// refused and reported as a securitypolicyviolation even though Zod falls back cleanly; jitless
// mode skips the probe. Every schema module imports this file first (SEC-P1 F3).
z.config({ jitless: true });
