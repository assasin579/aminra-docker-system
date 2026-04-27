import { Stack, router } from 'expo-router';
import { useEffect } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { useAuth } from '@/lib/AuthContext';
import { colors } from '@/lib/tokens';

export default function AppLayout() {
  const { token, loading } = useAuth();

  useEffect(() => {
    if (!loading && !token) router.replace('/(auth)/login');
  }, [token, loading]);

  if (loading || !token) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="visits/index" />
      <Stack.Screen name="visits/[id]/index" />
    </Stack>
  );
}
