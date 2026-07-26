import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import AdminPanelSettingsIcon from "@mui/icons-material/AdminPanelSettings";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, setCsrfToken } from "../api/client";
import { t } from "../i18n";

const schema = z.object({
  username: z.string().min(3),
  email: z.string().email().optional().or(z.literal("")),
  password: z.string().min(12),
  setup_token: z.string().optional()
});

type FormValues = z.infer<typeof schema>;

export function SetupPage() {
  const queryClient = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: "admin" }
  });

  const mutation = useMutation({
    mutationFn: api.bootstrap,
    onSuccess: (session) => {
      setCsrfToken(session.csrf_token);
      queryClient.invalidateQueries({ queryKey: ["setup-status"] });
      queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  });

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 3 }}>
      <Paper sx={{ width: "100%", maxWidth: 520, p: 4 }}>
        <Stack spacing={3}>
          <Box>
            <AdminPanelSettingsIcon color="primary" />
            <Typography variant="h4">{t("ui.079da89a50")}</Typography>
            <Typography color="text.secondary">
              {t("ui.f60f6f7747")}</Typography>
          </Box>
          {mutation.error && <Alert severity="error">{mutation.error.message}</Alert>}
          <Stack component="form" spacing={2} onSubmit={handleSubmit((values) => mutation.mutate(values))}>
            <TextField
              label={t("ui.e2d97c93ec")}
              autoComplete="username"
              error={Boolean(errors.username)}
              helperText={errors.username?.message}
              {...register("username")}
            />
            <TextField
              label="Email"
              autoComplete="email"
              error={Boolean(errors.email)}
              helperText={errors.email?.message}
              {...register("email")}
            />
            <TextField
              label={t("ui.14f7c63cc1")}
              type="password"
              autoComplete="new-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message || t("ui.e5a1c3460c")}
              {...register("password")}
            />
            <TextField label={t("field.setupToken")} type="password" {...register("setup_token")} />
            <Button
              type="submit"
              variant="contained"
              size="large"
              startIcon={<AdminPanelSettingsIcon />}
              disabled={mutation.isPending}
            >
              {t("ui.3ac094f23d")}</Button>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
}
