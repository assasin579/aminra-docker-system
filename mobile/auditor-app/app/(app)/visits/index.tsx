import { View, Text, ScrollView, TouchableOpacity, RefreshControl, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/AuthContext';
import { Visits, AuditVisit } from '@/lib/api';
import { colors, fontSize, fontWeight, radii, spacing } from '@/lib/tokens';

const STATUS_LABEL: Record<AuditVisit['status'], string> = {
  scheduled:        'Đã lên lịch',
  in_progress:      'Đang kiểm',
  completed:        'Đã kiểm xong',
  report_submitted: 'Đã có báo cáo',
};
const STATUS_COLOR: Record<AuditVisit['status'], string> = {
  scheduled:        colors.info,
  in_progress:      colors.warning,
  completed:        colors.success,
  report_submitted: colors.success,
};

function fmtDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' }); } catch { return iso; }
}

export default function VisitsListScreen() {
  const { token, user, signOut } = useAuth();
  const q = useQuery({
    queryKey: ['visits'],
    queryFn:  () => Visits.list(token!),
    enabled:  !!token,
  });
  const visits = q.data?.visits ?? [];
  const myVisits = user ? visits.filter(v => !v.auditor_id || v.auditor_id === user.id) : visits;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={['top']}>
      <View style={{ paddingHorizontal: spacing.xl, paddingTop: spacing.lg, paddingBottom: spacing.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <View style={{ flex: 1 }}>
          <Text style={{ fontSize: fontSize.xl, fontWeight: fontWeight.bold as '700', color: colors.text }}>Lịch kiểm định</Text>
          <Text style={{ fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 }}>{user?.company_name ?? ''}</Text>
        </View>
        <TouchableOpacity onPress={signOut} style={{ paddingHorizontal: spacing.md, paddingVertical: spacing.sm }}>
          <Text style={{ color: colors.textMuted, fontSize: fontSize.xs }}>Đăng xuất</Text>
        </TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: spacing.xxxl }}
        refreshControl={<RefreshControl refreshing={q.isFetching} onRefresh={() => q.refetch()} tintColor={colors.primary} />}>
        {q.isLoading ? (
          <View style={{ paddingVertical: spacing.xxxl, alignItems: 'center' }}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : q.isError ? (
          <View style={{ backgroundColor: colors.dangerBg, padding: spacing.lg, borderRadius: radii.lg }}>
            <Text style={{ color: colors.danger, fontSize: fontSize.sm }}>{(q.error as Error).message}</Text>
          </View>
        ) : myVisits.length === 0 ? (
          <View style={{ paddingVertical: spacing.xxxl, alignItems: 'center' }}>
            <Text style={{ color: colors.textSubtle, fontSize: fontSize.sm }}>Chưa có lịch kiểm nào.</Text>
          </View>
        ) : (
          myVisits.map(v => (
            <TouchableOpacity
              key={v.id}
              onPress={() => router.push(`/(app)/visits/${v.id}`)}
              style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.xl, padding: spacing.lg, marginBottom: spacing.md }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: spacing.sm }}>
                <View style={{ paddingHorizontal: 10, paddingVertical: 4, borderRadius: radii.full, backgroundColor: STATUS_COLOR[v.status] + '22' }}>
                  <Text style={{ fontSize: fontSize.xs, fontWeight: fontWeight.semibold as '600', color: STATUS_COLOR[v.status] }}>
                    {STATUS_LABEL[v.status]}
                  </Text>
                </View>
                <Text style={{ fontSize: fontSize.xs, color: colors.textSubtle }}>{fmtDate(v.scheduled_date)}</Text>
              </View>
              <Text style={{ fontSize: fontSize.md, fontWeight: fontWeight.semibold as '600', color: colors.text }} numberOfLines={1}>
                {v.business_name ?? 'Doanh nghiệp'}
              </Text>
              <Text style={{ fontSize: fontSize.xs, color: colors.textMuted, marginTop: 2 }}>
                {v.visit_type}{v.location ? ` · ${v.location}` : ''}
              </Text>
            </TouchableOpacity>
          ))
        )}
      </ScrollView>
    </SafeAreaView>
  );
}
