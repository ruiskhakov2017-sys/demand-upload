import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Box, Button, Link, Paper, Stack, TextField, Typography } from "@mui/material";
import LoginIcon from "@mui/icons-material/Login";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, setCsrfToken } from "../api/client";
import { t } from "../i18n";

const schema = z.object({
  username: z.string().min(1),
  password: z.string().min(1)
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const queryClient = useQueryClient();
  useEffect(() => {
    document.title = "Secure workspace | Axyro Analytics";
  }, []);
  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm<FormValues>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: api.login,
    onSuccess: (session) => {
      setCsrfToken(session.csrf_token);
      queryClient.invalidateQueries({ queryKey: ["me"] });
    }
  });

  return (
    <Box sx={{ minHeight: "100vh", display: "grid", placeItems: "center", p: 3 }}>
      <Paper sx={{ width: "100%", maxWidth: 420, p: 4 }}>
        <Stack spacing={3}>
          <Box>
            <Typography variant="overline" color="primary.main" fontWeight={800}>{t("app.productName")}</Typography>
            <Typography variant="h4" sx={{ mt: 0.5 }}>{t("ui.07205a06c3")}</Typography>
            <Typography color="text.secondary" sx={{ mt: 0.75 }}>{t("auth.secureWorkspace")}</Typography>
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
              label={t("ui.14f7c63cc1")}
              type="password"
              autoComplete="current-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register("password")}
            />
            <Button type="submit" variant="contained" size="large" startIcon={<LoginIcon />} disabled={mutation.isPending}>
              {t("ui.939e95a11d")}</Button>
          </Stack>
          <Link href="/" underline="hover" sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, width: "fit-content" }}>
            <ArrowBackIcon fontSize="small" />
            {t("auth.publicProductPage")}
          </Link>
        </Stack>
      </Paper>
    </Box>
  );
}
