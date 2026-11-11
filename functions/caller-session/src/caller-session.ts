import { StatefulActor } from "@telnyx/edge-runtime";

const VERIFIED_WINDOW_MS = 30 * 60 * 1000;
const LOCK_DURATION_MS = 15 * 60 * 1000;
const READY_DELAY_MS = 2 * 60 * 1000;
const MAX_ALARM_BACKOFF_MS = 60_000;

interface Refill {
  id: string;
  rxId: string;
  status: "submitted" | "ready";
  submittedAt: number;
  readyAt?: number;
}

function logLine(fields: Record<string, unknown>) {
  console.log(JSON.stringify(fields));
}

export class CallerSession extends StatefulActor {
  async recordCall(args: { traceId: string; callControlId?: string }): Promise<{
    callCount: number;
    locked: boolean;
    openRefills: number;
    lastIntent?: string;
    failedAttempts: number;
  }> {
    const start = Date.now();
    const callCount = ((await this.ctx.storage.get<number>("callCount")) ?? 0) + 1;
    const lockedUntil = (await this.ctx.storage.get<number>("lockedUntil")) ?? 0;
    const refills = (await this.ctx.storage.get<Refill[]>("refills")) ?? [];
    const openRefills = refills.filter((r) => r.status === "submitted").length;
    const lastIntent = await this.ctx.storage.get<string>("lastIntent");
    const failedAttempts = (await this.ctx.storage.get<number>("failedAttempts")) ?? 0;

    await this.ctx.storage.put("callCount", callCount);
    await this.ctx.storage.put("lastCallAt", Date.now());
    // Security: reset verification on every new call
    await this.ctx.storage.put("verifiedUntil", 0);

    logLine({
      actor: "CallerSession",
      event: "recordCall",
      traceId: args.traceId,
      callCount,
      locked: Date.now() < lockedUntil,
      openRefills,
      failedAttempts,
      latency_ms: Date.now() - start,
    });

    return { callCount, locked: Date.now() < lockedUntil, openRefills, lastIntent, failedAttempts };
  }

  async recordVerificationAttempt(args: {
    traceId: string;
    success: boolean;
    maxAttempts: number;
  }): Promise<{
    verified: boolean;
    failedAttempts: number;
    locked: boolean;
    lockedUntil?: number;
  }> {
    const start = Date.now();
    let failedAttempts = (await this.ctx.storage.get<number>("failedAttempts")) ?? 0;
    let lockedUntil = (await this.ctx.storage.get<number>("lockedUntil")) ?? 0;
    const now = Date.now();

    if (now < lockedUntil) {
      logLine({
        actor: "CallerSession",
        event: "recordVerificationAttempt",
        traceId: args.traceId,
        outcome: "already_locked",
        latency_ms: Date.now() - start,
      });
      return { verified: false, failedAttempts, locked: true, lockedUntil };
    }

    if (args.success) {
      failedAttempts = 0;
      lockedUntil = 0;
      await this.ctx.storage.put("failedAttempts", 0);
      await this.ctx.storage.put("lockedUntil", 0);
      await this.ctx.storage.put("verifiedUntil", now + VERIFIED_WINDOW_MS);
      logLine({
        actor: "CallerSession",
        event: "recordVerificationAttempt",
        traceId: args.traceId,
        outcome: "success",
        latency_ms: Date.now() - start,
      });
      return { verified: true, failedAttempts: 0, locked: false };
    }

    failedAttempts += 1;
    let newLockedUntil = 0;
    if (failedAttempts >= args.maxAttempts) {
      newLockedUntil = now + LOCK_DURATION_MS;
      await this.ctx.storage.put("lockedUntil", newLockedUntil);
    }
    await this.ctx.storage.put("failedAttempts", failedAttempts);

    logLine({
      actor: "CallerSession",
      event: "recordVerificationAttempt",
      traceId: args.traceId,
      outcome: "failure",
      failedAttempts,
      locked: newLockedUntil > 0,
      latency_ms: Date.now() - start,
    });

    return {
      verified: false,
      failedAttempts,
      locked: newLockedUntil > 0,
      lockedUntil: newLockedUntil || undefined,
    };
  }

  async isVerified(args: { traceId: string }): Promise<boolean> {
    const start = Date.now();
    const verifiedUntil = (await this.ctx.storage.get<number>("verifiedUntil")) ?? 0;
    const result = Date.now() < verifiedUntil;
    logLine({
      actor: "CallerSession",
      event: "isVerified",
      traceId: args.traceId,
      result,
      latency_ms: Date.now() - start,
    });
    return result;
  }

  async addRefill(args: { traceId: string; rxId: string }): Promise<{ refillId: string; status: string }> {
    const start = Date.now();
    const refills = (await this.ctx.storage.get<Refill[]>("refills")) ?? [];
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const newRefill: Refill = {
      id,
      rxId: args.rxId,
      status: "submitted",
      submittedAt: Date.now(),
    };
    refills.push(newRefill);
    await this.ctx.storage.put("refills", refills);

    const alarmTime = Date.now() + READY_DELAY_MS;
    await this.ctx.storage.setAlarm(alarmTime);

    logLine({
      actor: "CallerSession",
      event: "addRefill",
      traceId: args.traceId,
      rxId: args.rxId,
      refillId: id,
      alarmAt: alarmTime,
      latency_ms: Date.now() - start,
    });

    return { refillId: id, status: "submitted" };
  }

  async getRefills(args: { traceId: string }): Promise<Refill[]> {
    const start = Date.now();
    const refills = (await this.ctx.storage.get<Refill[]>("refills")) ?? [];
    logLine({
      actor: "CallerSession",
      event: "getRefills",
      traceId: args.traceId,
      count: refills.length,
      latency_ms: Date.now() - start,
    });
    return refills;
  }

  async setLastIntent(args: { traceId: string; intent: string }): Promise<void> {
    const start = Date.now();
    await this.ctx.storage.put("lastIntent", args.intent);
    logLine({
      actor: "CallerSession",
      event: "setLastIntent",
      traceId: args.traceId,
      intent: args.intent,
      latency_ms: Date.now() - start,
    });
  }

  async alarm(_info: unknown): Promise<void> {
    const start = Date.now();
    try {
      const refills = (await this.ctx.storage.get<Refill[]>("refills")) ?? [];
      const now = Date.now();
      const threshold = now - READY_DELAY_MS;
      let changed = false;
      let pending = 0;

      for (const r of refills) {
        if (r.status === "submitted" && r.submittedAt <= threshold) {
          r.status = "ready";
          r.readyAt = now;
          changed = true;
        }
        if (r.status === "submitted") {
          pending++;
        }
      }

      if (changed) {
        await this.ctx.storage.put("refills", refills);
      }

      if (pending > 0) {
        const nextAlarm = now + READY_DELAY_MS;
        await this.ctx.storage.setAlarm(nextAlarm);
        logLine({
          actor: "CallerSession",
          event: "alarm",
          outcome: "rearmed",
          pending,
          nextAlarm,
          latency_ms: Date.now() - start,
        });
      } else {
        logLine({
          actor: "CallerSession",
          event: "alarm",
          outcome: "done",
          latency_ms: Date.now() - start,
        });
      }
    } catch (err) {
      const backoff = Math.min(Date.now() + 5000, Date.now() + MAX_ALARM_BACKOFF_MS);
      await this.ctx.storage.setAlarm(backoff);
      logLine({
        actor: "CallerSession",
        event: "alarm",
        outcome: "error_rearmed",
        error: String(err),
        nextAlarm: backoff,
        latency_ms: Date.now() - start,
      });
    }
  }
}
