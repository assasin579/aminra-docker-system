import { useEffect } from 'react';
import { View, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { useAuth } from '@/lib/AuthContext';
import { colors } from '@/lib/tokens';

export default function Index() {
  const { token, loading } = useAuth();

  useEffect(() => {
    if (loading) return;
    router.replace(token ? '/(app)/visits' : '/(auth)/login');
  }, [token, loading]);

  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}>
      <ActivityIndicator color={colors.primary} size="large" />
    </View>
  );
}
