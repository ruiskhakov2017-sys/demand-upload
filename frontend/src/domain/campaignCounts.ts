export const QUICK_CAMPAIGN_COUNTS = [1, 3, 5, 7, 10] as const;

export function normalizeCampaignCount(value: number) {
  return Math.max(1, Math.min(500, Math.floor(value || 1)));
}

export function applyCampaignCount<T extends { customer_id: string; campaigns_count?: number }>(
  accounts: T[],
  customerIds: string[] | null,
  value: number
) {
  const count = normalizeCampaignCount(value);
  return accounts.map((account) => (
    customerIds === null || customerIds.includes(account.customer_id)
      ? { ...account, campaigns_count: count }
      : account
  ));
}
