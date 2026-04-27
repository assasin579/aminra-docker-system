import { useState, useRef } from 'react';
import { View, Text, TouchableOpacity, FlatList, Image, Alert, ActivityIndicator } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as ImageManipulator from 'expo-image-manipulator';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/lib/AuthContext';
import { Visits, Photos } from '@/lib/api';
import { colors, fontSize, fontWeight, radii, spacing } from '@/lib/tokens';

interface QueuedPhoto { uri: string; itemId: string; uploaded: boolean; error?: string }

/**
 * Photo capture per checklist item.
 * Flow: pick item → camera → capture → resize to 1600px → upload → mark uploaded.
 * If offline / upload fails, keep the URI in local state so user can retry.
 */
export default function VisitPhotosScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { token } = useAuth();
  const [permission, requestPermission] = useCameraPermissions();
  const [selectedItem, setSelectedItem] = useState<string | null>(null);
  const [photos, setPhotos] = useState<QueuedPhoto[]>([]);
  const cameraRef = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);

  const itemsQ = useQuery({
    queryKey: ['visit-items', id],
    queryFn: () => Visits.listItems(token!, id),
    enabled: !!token && !!id,
  });
  const items = itemsQ.data?.items ?? [];

  if (!permission) return null;

  if (!permission.granted) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: colors.background, padding: spacing.xl }}>
        <Text style={{ fontSize: fontSize.md, fontWeight: fontWeight.bold as '700', color: colors.text, marginBottom: spacing.md }}>
          Cần quyền camera
        </Text>
        <Text style={{ fontSize: fontSize.sm, color: colors.textMuted, marginBottom: spacing.xl, lineHeight: 20 }}>
          AMINRA Auditor cần truy cập camera để chụp ảnh bằng chứng từ hiện trường audit.
        </Text>
        <TouchableOpacity onPress={requestPermission} style={{ backgroundColor: colors.primary, paddingVertical: 14, borderRadius: radii.lg, alignItems: 'center' }}>
          <Text style={{ color: 'white', fontWeight: fontWeight.semibold as '600' }}>Cấp quyền camera</Text>
        </TouchableOpacity>
      </SafeAreaView>
    );
  }

  const capture = async () => {
    if (!selectedItem || !cameraRef.current) return;
    setBusy(true);
    try {
      const shot = await cameraRef.current.takePictureAsync({ quality: 0.85, skipProcessing: false });
      if (!shot?.uri) return;
      const resized = await ImageManipulator.manipulateAsync(
        shot.uri,
        [{ resize: { width: 1600 } }],
        { compress: 0.7, format: ImageManipulator.SaveFormat.JPEG },
      );
      const queue: QueuedPhoto = { uri: resized.uri, itemId: selectedItem, uploaded: false };
      setPhotos(p => [queue, ...p]);
      const result = await Photos.uploadForItem(token!, id, selectedItem, resized.uri);
      setPhotos(p => p.map(x => x.uri === queue.uri ? { ...x, uploaded: result.ok, error: result.ok ? undefined : result.detail } : x));
    } catch (e) {
      Alert.alert('Lỗi chụp ảnh', e instanceof Error ? e.message : 'Unknown');
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: '#000' }} edges={['top']}>
      <View style={{ paddingHorizontal: spacing.lg, paddingVertical: spacing.md, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, backgroundColor: '#000' }}>
        <TouchableOpacity onPress={() => router.back()} style={{ minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ color: 'white', fontSize: fontSize.lg }}>←</Text>
        </TouchableOpacity>
        <Text style={{ flex: 1, color: 'white', fontSize: fontSize.md, fontWeight: fontWeight.semibold as '600' }}>Chụp ảnh bằng chứng</Text>
      </View>

      <View style={{ flex: 1 }}>
        {selectedItem ? (
          <CameraView ref={cameraRef} style={{ flex: 1 }} facing="back" />
        ) : (
          <View style={{ flex: 1, padding: spacing.lg }}>
            <Text style={{ color: 'white', fontSize: fontSize.sm, marginBottom: spacing.md }}>Chọn item cần chụp ảnh:</Text>
            <FlatList
              data={items}
              keyExtractor={i => i.id}
              renderItem={({ item }) => (
                <TouchableOpacity
                  onPress={() => setSelectedItem(item.id)}
                  style={{ padding: spacing.md, backgroundColor: '#1a1a1a', borderRadius: radii.md, marginBottom: spacing.sm }}>
                  <Text style={{ color: 'white', fontSize: fontSize.sm }} numberOfLines={2}>{item.criteria}</Text>
                  <Text style={{ color: colors.textSubtle, fontSize: fontSize.xs, marginTop: 2 }}>{item.category}</Text>
                </TouchableOpacity>
              )}
            />
          </View>
        )}
      </View>

      {selectedItem && (
        <View style={{ padding: spacing.lg, backgroundColor: '#000', flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <TouchableOpacity onPress={() => setSelectedItem(null)} style={{ paddingVertical: spacing.sm, paddingHorizontal: spacing.md }}>
            <Text style={{ color: 'white' }}>Đổi item</Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={capture}
            disabled={busy}
            style={{ width: 64, height: 64, borderRadius: 32, backgroundColor: 'white', alignItems: 'center', justifyContent: 'center', borderWidth: 4, borderColor: colors.primary }}>
            {busy ? <ActivityIndicator color={colors.primary} /> : <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: colors.primary }} />}
          </TouchableOpacity>
          <Text style={{ color: 'white', fontSize: fontSize.xs, opacity: 0.7 }}>{photos.length} ảnh</Text>
        </View>
      )}

      {photos.length > 0 && (
        <View style={{ maxHeight: 100, backgroundColor: '#000', paddingHorizontal: spacing.md, paddingBottom: spacing.md }}>
          <FlatList
            horizontal
            data={photos}
            keyExtractor={p => p.uri}
            renderItem={({ item }) => (
              <View style={{ marginRight: spacing.sm, width: 72, height: 72, borderRadius: radii.md, overflow: 'hidden', position: 'relative' }}>
                <Image source={{ uri: item.uri }} style={{ width: '100%', height: '100%' }} />
                <View style={{ position: 'absolute', bottom: 4, right: 4, backgroundColor: item.uploaded ? colors.success : item.error ? colors.danger : colors.warning, borderRadius: radii.full, paddingHorizontal: 6, paddingVertical: 2 }}>
                  <Text style={{ color: 'white', fontSize: 10, fontWeight: fontWeight.bold as '700' }}>
                    {item.uploaded ? '✓' : item.error ? '✗' : '⋯'}
                  </Text>
                </View>
              </View>
            )}
          />
        </View>
      )}
    </SafeAreaView>
  );
}
