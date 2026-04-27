import { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, KeyboardAvoidingView, Platform, ScrollView, Image } from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAuth } from '@/lib/AuthContext';
import { colors, fontSize, fontWeight, radii, spacing } from '@/lib/tokens';

export default function LoginScreen() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async () => {
    setError('');
    setBusy(true);
    try {
      await signIn(email.trim().toLowerCase(), password);
      router.replace('/(app)/visits');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Đăng nhập thất bại');
    } finally {
      setBusy(false);
    }
  };

  const canSubmit = email.length > 3 && password.length >= 6 && !busy;

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.background }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
        <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: spacing.xl }} keyboardShouldPersistTaps="handled">
          <View style={{ alignItems: 'center', marginBottom: spacing.xxxl }}>
            <View style={{ width: 64, height: 64, borderRadius: radii.xl, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center', marginBottom: spacing.md }}>
              <Text style={{ color: 'white', fontSize: 28, fontWeight: fontWeight.black as '900' }}>A</Text>
            </View>
            <Text style={{ fontSize: fontSize.xl, fontWeight: fontWeight.bold as '700', color: colors.text }}>AMINRA Auditor</Text>
            <Text style={{ fontSize: fontSize.sm, color: colors.textMuted, marginTop: spacing.xs }}>Công cụ kiểm định tại nhà máy</Text>
          </View>

          <View style={{ marginBottom: spacing.lg }}>
            <Text style={{ fontSize: fontSize.xs, fontWeight: fontWeight.medium as '500', color: colors.textMuted, marginBottom: spacing.xs }}>Email tài khoản tổ chức</Text>
            <TextInput
              value={email}
              onChangeText={setEmail}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              placeholder="auditor@cb.example.vn"
              placeholderTextColor={colors.textSubtle}
              style={inputStyle}
            />
          </View>

          <View style={{ marginBottom: spacing.lg }}>
            <Text style={{ fontSize: fontSize.xs, fontWeight: fontWeight.medium as '500', color: colors.textMuted, marginBottom: spacing.xs }}>Mật khẩu</Text>
            <TextInput
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoCapitalize="none"
              placeholder="••••••••"
              placeholderTextColor={colors.textSubtle}
              style={inputStyle}
            />
          </View>

          {error ? (
            <View style={{ backgroundColor: colors.dangerBg, borderRadius: radii.md, padding: spacing.md, marginBottom: spacing.lg }}>
              <Text style={{ color: colors.danger, fontSize: fontSize.sm }}>{error}</Text>
            </View>
          ) : null}

          <TouchableOpacity
            onPress={onSubmit}
            disabled={!canSubmit}
            style={{
              backgroundColor: canSubmit ? colors.primary : colors.border,
              paddingVertical: 14,
              borderRadius: radii.lg,
              alignItems: 'center',
            }}>
            <Text style={{ color: canSubmit ? 'white' : colors.textMuted, fontSize: fontSize.base, fontWeight: fontWeight.semibold as '600' }}>
              {busy ? 'Đang đăng nhập...' : 'Đăng nhập'}
            </Text>
          </TouchableOpacity>

          <Text style={{ marginTop: spacing.xl, fontSize: fontSize.xs, color: colors.textSubtle, textAlign: 'center', lineHeight: 18 }}>
            App này chỉ dành cho tổ chức cấp chứng nhận (provider) và auditor được phân công.
            Sử dụng cùng tài khoản như aminra.vn.
          </Text>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const inputStyle = {
  backgroundColor: colors.surface,
  borderWidth: 1,
  borderColor: colors.border,
  borderRadius: radii.lg,
  paddingHorizontal: spacing.lg,
  paddingVertical: 14,
  fontSize: fontSize.base,
  color: colors.text,
};
