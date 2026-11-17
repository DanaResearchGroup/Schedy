// Whether the planner can release graduate pins. The server owns the list of
// pins (`GET /terms/{t}/grad-pins`), so a reload, a term switch or a solve that
// failed on a pin all see them; session metadata is empty until a solve succeeds.
export function showReleaseGradPins(
  pinned: Record<string, unknown>, published: boolean,
): boolean {
  return !published && Object.keys(pinned).length > 0;
}
