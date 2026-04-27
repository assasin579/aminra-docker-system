import { View, Text, ScrollView, TouchableOpacity, ActivityIndicator, Alert } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/AuthContext';
import { Visits, ChecklistItem, AuditVisit } from '@/lib/api';
import { colors, fontSize, fontWeight, radii, spacing } from '@/lib/tokens';

const ITEM_STATUS_LABEL: Record<ChecklistItem['status'], string> = {
  pending: '—',
  pass:    '✓ Đạt',
  fail:    '✗ Không đạt',
  na:      'N/A',
};
const ITEM_STATUS_COLOR: Record<ChecklistItem['status'], string> = {
  pending: colors.textSubtle,
  pass:    colors.success,
  fail:    colors.danger,
  na:      colors.textMuted,
};

export default function VisitDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { token } = useAuth();
  const qc = useQueryClient();

  const visitQ = useQuery({
    queryKey: ['visit', id],
    queryFn: () => Visits.get(token!, id),
    enabled: !!token && !!id,
  });
  const itemsQ = useQuery({
    queryKey: ['visit-items', id],
    queryFn: () => Visits.listItems(token!, id),
    enabled: !!token && !!id,
  });

  const updateItem = useMutation({
    mutationFn: ({ itemId, status }: { itemId: string; status: ChecklistItem['status'] }) =>
      Visits.updateItem(token!, id, itemId, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['visit-items', id] }),
  });

  const startVisit = useMutation({
    mutationFn: () => Visits.updateStatus(token!, id, 'in_progress'),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['visit', id] }),
  });

  const visit = visitQ.data;
  const items = itemsQ.data?.items ?? [];
  const grouped = groupBy(items, i => i.category);

  if (visitQ.isLoading) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.primary} />
      </SafeAreaView>
    );
  }
  if (!visit) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background, padding: spacing.lg }}>
        <Text style={{ color: colors.danger }}>Không tìm thấy lịch kiểm</Text>
      </SafeAreaView>
    );
  }

  const passCount = items.filter(i => i.status === 'pass').length;
  const failCount = items.filter(i => i.status === 'fail').length;
  const total = items.length;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={['top']}>
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.sm, flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
        <TouchableOpacity onPress={() => router.back()} style={{ paddingVertical: spacing.sm, paddingHorizontal: spacing.sm, minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: colors.primary, fontSize: fontSize.base, fontWeight: fontWeight.semibold as '600' }}>←</Text>
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: fontSize.lg, fontWeight: fontWeight.bold as '700', color: colors.text }} numberOfLines={1}>
          {visit.business_name ?? 'Audit'}
        </Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxxl, gap: spacing.md }}>
        {/* Visit summary card */}
        <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.xl, padding: spacing.lg, gap: spacing.sm }}>
          <Row label="Loại kiểm" value={visit.visit_type} />
          <Row label="Ngày kiểm" value={new Date(visit.scheduled_date).toLocaleDateString('vi-VN')} />
          {visit.location ? <Row label="Địa điểm" value={visit.location} /> : null}
          <Row label="Trạng thái" value={visit.status} valueColor={statusColor(visit.status)} />
          <Row label="Tiến độ" value={`${passCount}/${total} đạt · ${failCount} lỗi`} />
        </View>

        {visit.status === 'scheduled' && (
          <TouchableOpacity
            onPress={() => {
              Alert.alert('Bắt đầu kiểm', 'Đánh dấu kiểm định đang tiến hành?', [
                { text: 'Hủy', style: 'cancel' },
                { text: 'Bắt đầu', onPress: () => startVisit.mutate() },
              ]);
            }}
            disabled={startVisit.isPending}
            style={{ backgroundColor: colors.primary, paddingVertical: 14, borderRadius: radii.lg, alignItems: 'center' }}>
            <Text style={{ color: 'white', fontSize: fontSize.base, fontWeight: fontWeight.semibold as '600' }}>
              {startVisit.isPending ? 'Đang cập nhật...' : '▶ Bắt đầu kiểm tra'}
            </Text>
          </TouchableOpacity>
        )}

        {visit.status === 'in_progress' && (
          <View style={{ flexDirection: 'row', gap: spacing.sm }}>
            <TouchableOpacity
              onPress={() => router.push(`/(app)/visits/${id}/photos`)}
              style={{ flex: 1, backgroundColor: colors.primaryLight, borderWidth: 1, borderColor: colors.primaryBorder, paddingVertical: 14, borderRadius: radii.lg, alignItems: 'center' }}>
              <Text style={{ color: colors.primary, fontSize: fontSize.sm, fontWeight: fontWeight.semibold as '600' }}>📷 Chụp ảnh</Text>
            </TouchableOpacity>
            <TouchableOpacity
              onPress={() => router.push(`/(app)/visits/${id}/sign-off`)}
              style={{ flex: 1, backgroundColor: colors.primary, paddingVertical: 14, borderRadius: radii.lg, alignItems: 'center' }}>
              <Text style={{ color: 'white', fontSize: fontSize.sm, fontWeight: fontWeight.semibold as '600' }}>✓ Hoàn tất</Text>
            </TouchableOpacity>
          </View>
        )}

        {/* Checklist grouped by category */}
        {itemsQ.isLoading ? (
          <ActivityIndicator color={colors.primary} />
        ) : (
          Object.entries(grouped).map(([category, list]) => (
            <View key={category} style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.xl, overflow: 'hidden' }}>
              <View style={{ paddingHorizontal: spacing.lg, paddingVertical: spacing.md, backgroundColor: colors.background, borderBottomWidth: 1, borderColor: colors.border }}>
                <Text style={{ fontSize: fontSize.sm, fontWeight: fontWeight.semibold as '600', color: colors.text }}>{category}</Text>
              </View>
              {list.map((item, i) => (
                <View key={item.id} style={{ padding: spacing.lg, gap: spacing.sm, borderBottomWidth: i < list.length - 1 ? 1 : 0, borderColor: colors.border }}>
                  <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm }}>
                    {item.severity === 'critical' && (
                      <View style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: radii.sm, backgroundColor: colors.dangerBg }}>
                        <Text style={{ fontSize: 10, fontWeight: fontWeight.bold as '700', color: colors.danger }}>QUAN TRỌNG</Text>
                      </View>
                    )}
                    <Text style={{ flex: 1, fontSize: fontSize.sm, color: colors.text, lineHeight: 20 }}>{item.criteria}</Text>
                  </View>
                  <View style={{ flexDirection: 'row', gap: spacing.xs, flexWrap: 'wrap' }}>
                    {(['pass', 'fail', 'na'] as const).map(s => {
                      const active = item.status === s;
                      const c = ITEM_STATUS_COLOR[s];
                      return (
                        <TouchableOpacity
                          key={s}
                          onPress={() => updateItem.mutate({ itemId: item.id, status: s })}
                          style={{
                            paddingHorizontal: spacing.md,
                            paddingVertical: 8,
                            borderRadius: radii.md,
                            borderWidth: 1,
                            borderColor: active ? c : colors.border,
                            backgroundColor: active ? c + '20' : colors.surface,
                            minWidth: 80,
                            alignItems: 'center',
                          }}>
                          <Text style={{ fontSize: fontSize.xs, fontWeight: fontWeight.semibold as '600', color: active ? c : colors.textMuted }}>
                            {ITEM_STATUS_LABEL[s]}
                          </Text>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                </View>
              ))}
            </View>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

function Row({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md }}>
      <Text style={{ fontSize: fontSize.xs, color: colors.textMuted }}>{label}</Text>
      <Text style={{ fontSize: fontSize.sm, color: valueColor ?? colors.text, fontWeight: fontWeight.medium as '500', flex: 1, textAlign: 'right' }}>{value}</Text>
    </View>
  );
}

function statusColor(s: AuditVisit['status']) {
  switch (s) {
    case 'scheduled':        return colors.info;
    case 'in_progress':      return colors.warning;
    case 'completed':
    case 'report_submitted': return colors.success;
    default:                 return colors.text;
  }
}

function groupBy<T, K extends string>(arr: T[], fn: (x: T) => K): Record<K, T[]> {
  return arr.reduce((acc, x) => {
    const k = fn(x);
    (acc[k] ||= []).push(x);
    return acc;
  }, {} as Record<K, T[]>);
}
