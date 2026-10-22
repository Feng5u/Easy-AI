export function adaptStyleNonce(code: string, id: string): string | null;
export function styleNoncePlugin(): {
  name: string;
  enforce: "pre";
  transform(code: string, id: string): { code: string; map: null } | null;
};
