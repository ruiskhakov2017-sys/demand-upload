import { zodResolver } from "@hookform/resolvers/zod";
import { Alert, Box, Button, Paper, Stack, TextField, Typography } from "@mui/material";
import LoginIcon from "@mui/icons-material/Login";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { api, setCsrfToken } from "../api/client";

const schema = z.object({
  username: z.string().min(1),
  password: z.string().min(1)
});

type FormValues = z.infer<typeof schema>;

export function LoginPage() {
  const queryClient = useQueryClient();
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
            <Typography variant="h4">Вход</Typography>
            <Typography color="text.secondary">Защищённая панель Demand Gen Uploader</Typography>
          </Box>
          {mutation.error && <Alert severity="error">{mutation.error.message}</Alert>}
          <Stack component="form" spacing={2} onSubmit={handleSubmit((values) => mutation.mutate(values))}>
            <TextField
              label="Логин"
              autoComplete="username"
              error={Boolean(errors.username)}
              helperText={errors.username?.message}
              {...register("username")}
            />
            <TextField
              label="Пароль"
              type="password"
              autoComplete="current-password"
              error={Boolean(errors.password)}
              helperText={errors.password?.message}
              {...register("password")}
            />
            <Button type="submit" variant="contained" size="large" startIcon={<LoginIcon />} disabled={mutation.isPending}>
              Войти
            </Button>
          </Stack>
        </Stack>
      </Paper>
    </Box>
  );
}

