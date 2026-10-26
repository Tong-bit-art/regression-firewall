export function createSession(user: string, ttl = 3600): string {
  return `session:${user}`;
}

export const VERSION = "1.0.0";
