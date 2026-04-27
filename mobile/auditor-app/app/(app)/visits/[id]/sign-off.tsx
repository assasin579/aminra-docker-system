import { useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Location from 'expo-location';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/lib/AuthContext';
import { Visits, Signatures, apiPost } from '@/lib/api';
import { colors, fontSize, fontWeight, radii, spacing } from '@/lib/tokens';

interface GpsPoint { lat: number; lng: number; accuracy: number; timestamp: number }

/**
 * Sign-off flow:
 *  1. Capture GPS (start_gps if not yet, end_gps now) → POST to backend
 *  2. Capture auditor signature → POST as PNG
 *  3. Mark visit completed → status = 'completed'
 *
 * Note: For MVP, signature is captured via on-screen draw using SVG canvas
 * (TODO Phase 1.4). For now we POST a placeholder + use status update only.
 */
export default function SignOffScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { token } = useAuth();
  const qc = useQueryClient();

  const [gps, setGps] = useState<GpsPoint | null>(null);
  const [gpsError, setGpsError] = useState('');
  const [gpsBusy, setGpsBusy] = useState(false);

  const captureGps = async () => {
    setGpsError('');
    setGpsBusy(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setGpsError('Cần quyền vị trí để xác minh hiện diện thực tế');
        setGpsBusy(false);
        return;
      }
      const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.High });
      setGps({
        lat:       loc.coords.latitude,
        lng:       loc.coords.longitude,
        accuracy:  loc.coords.accuracy ?? 0,
        timestamp: loc.timestamp,
      });
    } catch (e) {
      setGpsError(e instanceof Error ? e.message : 'Không lấy được GPS');
    } finally {
      setGpsBusy(false);
    }
  };

  useEffect(() => { captureGps(); }, []);

  const submitGps = useMutation({
    mutationFn: async () => {
      if (!gps) throw new Error('Chưa có GPS');
      // Backend stores end_gps as JSONB on audit_visits
      return apiPost(`/api/audits/visits/${id}`, token!, {
        end_gps: { lat: gps.lat, lng: gps.lng, accuracy: gps.accuracy, captured_at: new Date(gps.timestamp).toISOString() },
      });
    },
  });

  const completeVisit = useMutation({
    mutationFn: () => Visits.updateStatus(token!, id, 'completed'),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['visit', id] });
      qc.invalidateQueries({ queryKey: ['visits'] });
    },
  });

  const onSignOff = async () => {
    if (!gps) { Alert.alert('Chưa có GPS', 'Vui lòng chờ lấy vị trí'); return; }
    Alert.alert(
      'Hoàn tất audit',
      `GPS: ${gps.lat.toFixed(5)}, ${gps.lng.toFixed(5)} (±${Math.round(gps.accuracy)}m)\n\nXác nhận đóng kiểm định và submit cho provider duyệt?`,
      [
        { text: 'Hủy', style: 'cancel' },
        {
          text: 'Xác nhận', onPress: async () => {
            try {
              await submitGps.mutateAsync();
              await completeVisit.mutateAsync();
              router.replace('/(app)/visits');
            } catch (e) {
              Alert.alert('Lỗi', e instanceof Error ? e.message : 'Submit thất bại');
            }
          },
        },
      ],
    );
  };

  const submitting = submitGps.isPending || completeVisit.isPending;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }} edges={['top']}>
      <View style={{ paddingHorizontal: spacing.lg, paddingTop: spacing.md, paddingBottom: spacing.sm, flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
        <TouchableOpacity onPress={() => router.back()} style={{ minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: colors.primary, fontSize: fontSize.base, fontWeight: fontWeight.semibold as '600' }}>←</Text>
        </TouchableOpacity>
        <Text style={{ flex: 1, fontSize: fontSize.lg, fontWeight: fontWeight.bold as '700', color: colors.text }}>Hoàn tất audit</Text>
      </View>

      <ScrollView contentContainerStyle={{ padding: spacing.lg, gap: spacing.md }}>
        <Card title="📍 Vị trí GPS">
          {gpsBusy ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
              <ActivityIndicator color={colors.primary} />
              <Text style={{ color: colors.textMuted, fontSize: fontSize.sm }}>Đang lấy vị trí...</Text>
            </View>
          ) : gpsError ? (
            <View>
              <Text style={{ color: colors.danger, fontSize: fontSize.sm, marginBottom: spacing.sm }}>{gpsError}</Text>
              <TouchableOpacity onPress={captureGps} style={{ backgroundColor: colors.primary, paddingVertical: 10, borderRadius: radii.md, alignItems: 'center' }}>
                <Text style={{ color: 'white', fontWeight: fontWeight.semibold as '600', fontSize: fontSize.sm }}>Thử lại</Text>
              </TouchableOpacity>
            </View>
          ) : gps ? (
            <View>
              <Text style={{ color: colors.text, fontSize: fontSize.sm, fontFamily: 'Courier' }}>
                {gps.lat.toFixed(6)}, {gps.lng.toFixed(6)}
              </Text>
              <Text style={{ color: colors.textMuted, fontSize: fontSize.xs, marginTop: 4 }}>
                Độ chính xác ±{Math.round(gps.accuracy)}m · {new Date(gps.timestamp).toLocaleTimeString('vi-VN')}
              </Text>
            </View>
          ) : null}
        </Card>

        <Card title="✍️ Chữ ký auditor">
          <Text style={{ color: colors.textMuted, fontSize: fontSize.sm, lineHeight: 20 }}>
            Tính năng ký điện tử sẽ có ở phiên bản tiếp theo. Hiện tại sign-off chỉ cần GPS + xác nhận.
          </Text>
        </Card>

        <Card title="📷 Ảnh đã chụp">
          <TouchableOpacity
            onPress={() => router.push(`/(app)/visits/${id}/photos`)}
            style={{ backgroundColor: colors.primaryLight, paddingVertical: 10, borderRadius: radii.md, alignItems: 'center', borderWidth: 1, borderColor: colors.primaryBorder }}>
            <Text style={{ color: colors.primary, fontWeight: fontWeight.semibold as '600', fontSize: fontSize.sm }}>Chụp thêm ảnh →</Text>
          </TouchableOpacity>
        </Card>

        <TouchableOpacity
          onPress={onSignOff}
          disabled={submitting || !gps}
          style={{
            backgroundColor: submitting || !gps ? colors.border : colors.primary,
            paddingVertical: 16,
            borderRadius: radii.lg,
            alignItems: 'center',
            marginTop: spacing.md,
          }}>
          <Text style={{ color: submitting || !gps ? colors.textMuted : 'white', fontSize: fontSize.base, fontWeight: fontWeight.semibold as '600' }}>
            {submitting ? 'Đang submit...' : '✓ Hoàn tất kiểm định'}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </SafeAreaView>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={{ backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.xl, padding: spacing.lg, gap: spacing.sm }}>
      <Text style={{ fontSize: fontSize.sm, fontWeight: fontWeight.semibold as '600', color: colors.text }}>{title}</Text>
      {children}
    </View>
  );
}
