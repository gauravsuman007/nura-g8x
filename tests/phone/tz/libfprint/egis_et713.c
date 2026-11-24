/*
 * Egistec ET713 in-display (optical, match-on-chip) sensor of the LG G8x, through egistad.
 *
 * The trustlet that drives the sensor needs a QSEE file listener, the panel's LHBM spot and the touchscreen's
 * finger-down, so a root daemon (egistad) owns all of that and serves a small line protocol on a unix socket:
 *   LIST -> "FIDS a b ..."; ENROLL -> TOUCH/RETRY x/PROGRESS pct ... DONE fid; IDENTIFY -> TOUCH/RETRY x ...
 *   MATCH fid | NOMATCH; DELETE fid -> OK; CANCEL aborts a running ENROLL/IDENTIFY ("ERR cancelled").
 * Templates live in the trustlet; prints carry the trustlet finger id ("(u)" fpi-data).
 *
 * The device is announced through the virtual-device mechanism: FP_EGISTA=<socket path> in fprintd's environment.
 *
 * SPDX-License-Identifier: LGPL-2.1-or-later
 */

#define FP_COMPONENT "egis_et713"

#include "drivers_api.h"
#include <gio/gio.h>
#include <gio/gunixsocketaddress.h>
#include <stdio.h>
#include <stdlib.h>

#define ENROLL_STAGES 20

struct _FpiDeviceEgisEt713
{
  FpDevice           parent;
  gchar             *path;
  GSocketConnection *conn;
  GDataInputStream  *in;
  GCancellable      *op_cancel;
  gint               stage;
  GMainContext      *ctx;          /* libfprint's context, for reports from the worker thread */
};

G_DECLARE_FINAL_TYPE (FpiDeviceEgisEt713, fpi_device_egis_et713, FPI, DEVICE_EGIS_ET713, FpDevice)
G_DEFINE_TYPE (FpiDeviceEgisEt713, fpi_device_egis_et713, FP_TYPE_DEVICE)

static const FpIdEntry id_table[] = {
  { .virtual_envvar = "FP_EGISTA", },
  { .virtual_envvar = NULL }
};

/* ---- socket helpers (run in a worker thread) ---- */

static gboolean
et_connect (FpiDeviceEgisEt713 *self, GError **error)
{
  g_autoptr(GSocketClient) client = g_socket_client_new ();
  g_autoptr(GSocketAddress) addr = g_unix_socket_address_new (self->path);

  g_clear_object (&self->in);
  g_clear_object (&self->conn);
  self->conn = g_socket_client_connect (client, G_SOCKET_CONNECTABLE (addr), NULL, error);
  if (!self->conn)
    return FALSE;
  self->in = g_data_input_stream_new (g_io_stream_get_input_stream (G_IO_STREAM (self->conn)));
  return TRUE;
}

static gboolean
et_send (FpiDeviceEgisEt713 *self, const gchar *line, GError **error)
{
  g_autofree gchar *l = g_strconcat (line, "\n", NULL);
  GOutputStream *out = g_io_stream_get_output_stream (G_IO_STREAM (self->conn));

  return g_output_stream_write_all (out, l, strlen (l), NULL, NULL, error);
}

static gchar *
et_read (FpiDeviceEgisEt713 *self, GError **error)
{
  gchar *l = g_data_input_stream_read_line (self->in, NULL, NULL, error);

  if (!l && error && !*error)
    g_set_error (error, G_IO_ERROR, G_IO_ERROR_CLOSED, "egistad closed the connection");
  return l;
}

/* An in-flight ENROLL/IDENTIFY is aborted by sending CANCEL on the same connection. */
static void
on_op_cancelled (GCancellable *c, gpointer user_data)
{
  FpiDeviceEgisEt713 *self = user_data;

  if (self->conn)
    {
      GOutputStream *out = g_io_stream_get_output_stream (G_IO_STREAM (self->conn));
      g_output_stream_write_all (out, "CANCEL\n", 7, NULL, NULL, NULL);
    }
}

static GError *
map_error (GError *e)
{
  if (!e)
    return fpi_device_error_new (FP_DEVICE_ERROR_GENERAL);
  if (g_error_matches (e, G_IO_ERROR, G_IO_ERROR_CANCELLED))
    return e;
  return fpi_device_error_new_msg (FP_DEVICE_ERROR_PROTO, "egistad: %s", e->message);
}

static FpPrint *
print_for_fid (FpDevice *dev, guint fid)
{
  FpPrint *print = fp_print_new (dev);
  g_autofree gchar *desc = g_strdup_printf ("ET713 finger %u", fid);

  fpi_print_set_type (print, FPI_PRINT_RAW);
  fpi_print_set_device_stored (print, TRUE);
  g_object_set (print, "fpi-data", g_variant_new ("(u)", fid), "description", desc, NULL);
  return print;
}

static guint
fid_of (FpPrint *print)
{
  g_autoptr(GVariant) data = NULL;
  guint fid = 0;

  g_object_get (print, "fpi-data", &data, NULL);
  if (data && g_variant_is_of_type (data, G_VARIANT_TYPE ("(u)")))
    g_variant_get (data, "(u)", &fid);
  return fid;
}

/* ---- progress reports marshalled to the main context ---- */

typedef struct
{
  FpDevice *dev;
  gint      kind;               /* 0 = progress, 1 = retry */
  gint      stage;
} Report;

static gboolean
report_idle (gpointer data)
{
  Report *r = data;

  if (r->kind == 0)
    fpi_device_enroll_progress (r->dev, r->stage, NULL, NULL);
  else if (fpi_device_get_current_action (r->dev) == FPI_DEVICE_ACTION_ENROLL)
    fpi_device_enroll_progress (r->dev, r->stage, NULL, fpi_device_retry_new (FP_DEVICE_RETRY_CENTER_FINGER));
  g_object_unref (r->dev);
  g_free (r);
  return G_SOURCE_REMOVE;
}

static void
report (FpDevice *dev, gint kind, gint stage)
{
  Report *r = g_new0 (Report, 1);

  r->dev = g_object_ref (dev);
  r->kind = kind;
  r->stage = stage;
  g_main_context_invoke (FPI_DEVICE_EGIS_ET713 (dev)->ctx, report_idle, r);
}

/* ---- worker threads ---- */

static void
open_thread (GTask *task, gpointer src, gpointer data, GCancellable *c)
{
  FpiDeviceEgisEt713 *self = src;
  GError *error = NULL;

  if (!et_connect (self, &error))
    return g_task_return_error (task, error);
  g_task_return_boolean (task, TRUE);
}

static void
enroll_thread (GTask *task, gpointer src, gpointer data, GCancellable *c)
{
  FpiDeviceEgisEt713 *self = src;
  GError *error = NULL;

  if (!et_send (self, "ENROLL", &error))
    return g_task_return_error (task, error);
  for (;;)
    {
      g_autofree gchar *l = et_read (self, &error);
      gint pct;

      if (!l)
        return g_task_return_error (task, error);
      if (sscanf (l, "PROGRESS %d", &pct) == 1)
        {
          /* map 0..100 % onto stages; the last stage is reported with the completion */
          gint s = MIN (ENROLL_STAGES - 1, pct * ENROLL_STAGES / 100);
          while (self->stage < s)
            report (FP_DEVICE (self), 0, ++self->stage);
        }
      else if (g_str_has_prefix (l, "RETRY"))
        report (FP_DEVICE (self), 1, self->stage);
      else if (g_str_has_prefix (l, "DONE "))
        return g_task_return_int (task, atoi (l + 5));
      else if (g_str_has_prefix (l, "ERR cancelled"))
        return g_task_return_new_error (task, G_IO_ERROR, G_IO_ERROR_CANCELLED, "cancelled");
      else if (g_str_has_prefix (l, "ERR"))
        return g_task_return_new_error (task, G_IO_ERROR, G_IO_ERROR_FAILED, "%s", l);
    }
}

static void
identify_thread (GTask *task, gpointer src, gpointer data, GCancellable *c)
{
  FpiDeviceEgisEt713 *self = src;
  GError *error = NULL;

  if (!et_send (self, "IDENTIFY", &error))
    return g_task_return_error (task, error);
  for (;;)
    {
      g_autofree gchar *l = et_read (self, &error);

      if (!l)
        return g_task_return_error (task, error);
      if (g_str_has_prefix (l, "MATCH "))
        return g_task_return_int (task, atoi (l + 6));
      if (g_str_has_prefix (l, "NOMATCH"))
        return g_task_return_int (task, 0);
      if (g_str_has_prefix (l, "ERR cancelled"))
        return g_task_return_new_error (task, G_IO_ERROR, G_IO_ERROR_CANCELLED, "cancelled");
      if (g_str_has_prefix (l, "ERR"))
        return g_task_return_new_error (task, G_IO_ERROR, G_IO_ERROR_FAILED, "%s", l);
    }
}

static void
simple_thread (GTask *task, gpointer src, gpointer data, GCancellable *c)
{
  FpiDeviceEgisEt713 *self = src;
  GError *error = NULL;
  g_autofree gchar *l = NULL;

  if (!et_send (self, data, &error) || !(l = et_read (self, &error)))
    return g_task_return_error (task, error);
  g_task_return_pointer (task, g_steal_pointer (&l), g_free);
}

static void
run (FpiDeviceEgisEt713 *self, GTaskThreadFunc fn, gchar *arg, GAsyncReadyCallback cb)
{
  g_autoptr(GTask) task = g_task_new (self, NULL, cb, NULL);

  if (arg)
    g_task_set_task_data (task, arg, g_free);
  g_task_run_in_thread (task, fn);
}

/* ---- FpDevice vfuncs ---- */

static void
open_done (GObject *src, GAsyncResult *res, gpointer d)
{
  GError *error = NULL;

  g_task_propagate_boolean (G_TASK (res), &error);
  fpi_device_open_complete (FP_DEVICE (src), error ? map_error (error) : NULL);
}

static void
dev_open (FpDevice *dev)
{
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (dev);

  g_free (self->path);
  self->path = g_strdup (fpi_device_get_virtual_env (dev));
  if (!self->ctx)
    self->ctx = g_main_context_ref_thread_default ();
  run (self, open_thread, NULL, open_done);
}

static void
dev_close (FpDevice *dev)
{
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (dev);

  g_clear_object (&self->in);
  if (self->conn)
    g_io_stream_close (G_IO_STREAM (self->conn), NULL, NULL);
  g_clear_object (&self->conn);
  fpi_device_close_complete (dev, NULL);
}

static void
op_begin (FpiDeviceEgisEt713 *self)
{
}

static void
enroll_done (GObject *src, GAsyncResult *res, gpointer d)
{
  FpDevice *dev = FP_DEVICE (src);
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (dev);
  GError *error = NULL;
  gssize fid = g_task_propagate_int (G_TASK (res), &error);
  FpPrint *print = NULL;
  g_autofree gchar *uid = NULL;

  if (error)
    return fpi_device_enroll_complete (dev, NULL, map_error (error));
  while (self->stage < ENROLL_STAGES)
    fpi_device_enroll_progress (dev, ++self->stage, NULL, NULL);
  fpi_device_get_enroll_data (dev, &print);
  fpi_print_set_type (print, FPI_PRINT_RAW);
  fpi_print_set_device_stored (print, TRUE);
  g_object_set (print, "fpi-data", g_variant_new ("(u)", (guint) fid), NULL);
  uid = fpi_print_generate_user_id (print);
  fpi_print_fill_from_user_id (print, uid);
  fpi_device_enroll_complete (dev, g_object_ref (print), NULL);
}

static void
dev_enroll (FpDevice *dev)
{
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (dev);

  self->stage = 0;
  op_begin (self);
  run (self, enroll_thread, NULL, enroll_done);
}

static void
identify_done (GObject *src, GAsyncResult *res, gpointer d)
{
  FpDevice *dev = FP_DEVICE (src);
  GError *error = NULL;
  gssize fid = g_task_propagate_int (G_TASK (res), &error);
  gboolean verify = fpi_device_get_current_action (dev) == FPI_DEVICE_ACTION_VERIFY;
  FpPrint *found = NULL;

  if (error)
    {
      error = map_error (error);
      if (verify)
        return fpi_device_verify_complete (dev, error);
      return fpi_device_identify_complete (dev, error);
    }

  if (verify)
    {
      FpPrint *print = NULL;

      fpi_device_get_verify_data (dev, &print);
      if (fid && fid_of (print) == (guint) fid)
        fpi_device_verify_report (dev, FPI_MATCH_SUCCESS, print_for_fid (dev, fid), NULL);
      else
        fpi_device_verify_report (dev, FPI_MATCH_FAIL, fid ? print_for_fid (dev, fid) : NULL, NULL);
      return fpi_device_verify_complete (dev, NULL);
    }
  else
    {
      GPtrArray *prints = NULL;

      fpi_device_get_identify_data (dev, &prints);
      for (guint i = 0; fid && i < prints->len; i++)
        if (fid_of (g_ptr_array_index (prints, i)) == (guint) fid)
          found = g_ptr_array_index (prints, i);
      fpi_device_identify_report (dev, found, fid ? print_for_fid (dev, fid) : NULL, NULL);
      fpi_device_identify_complete (dev, NULL);
    }
}

static void
dev_identify (FpDevice *dev)
{
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (dev);

  op_begin (self);
  run (self, identify_thread, NULL, identify_done);
}

static void
list_done (GObject *src, GAsyncResult *res, gpointer d)
{
  FpDevice *dev = FP_DEVICE (src);
  GError *error = NULL;
  g_autofree gchar *l = g_task_propagate_pointer (G_TASK (res), &error);
  GPtrArray *prints;
  g_auto(GStrv) w = NULL;

  if (!l)
    return fpi_device_list_complete (dev, NULL, map_error (error));
  prints = g_ptr_array_new_with_free_func (g_object_unref);
  w = g_strsplit (l, " ", -1);
  for (gint i = 1; w[0] && g_str_equal (w[0], "FIDS") && w[i]; i++)
    if (atoi (w[i]) > 0)
      g_ptr_array_add (prints, print_for_fid (dev, atoi (w[i])));
  fpi_device_list_complete (dev, prints, NULL);
}

static void
dev_list (FpDevice *dev)
{
  run (FPI_DEVICE_EGIS_ET713 (dev), simple_thread, g_strdup ("LIST"), list_done);
}

static void
delete_done (GObject *src, GAsyncResult *res, gpointer d)
{
  GError *error = NULL;
  g_autofree gchar *l = g_task_propagate_pointer (G_TASK (res), &error);

  if (!l)
    return fpi_device_delete_complete (FP_DEVICE (src), map_error (error));
  fpi_device_delete_complete (FP_DEVICE (src), g_str_has_prefix (l, "OK") ? NULL :
                              fpi_device_error_new_msg (FP_DEVICE_ERROR_DATA_NOT_FOUND, "%s", l));
}

static void
dev_delete (FpDevice *dev)
{
  FpPrint *print = NULL;

  fpi_device_get_delete_data (dev, &print);
  run (FPI_DEVICE_EGIS_ET713 (dev), simple_thread, g_strdup_printf ("DELETE %u", fid_of (print)), delete_done);
}

static void
dev_cancel (FpDevice *dev)
{
  on_op_cancelled (NULL, FPI_DEVICE_EGIS_ET713 (dev));
}

/* Without these libfprint cancels a running verify when the system suspends ("Cannot run while suspended"):
 * the lock screen's fingerprint conversation then ended and was not restarted. The wait lives in egistad
 * (a socket read), which simply continues after resume, so suspend and resume only have to say yes. */
static void
dev_suspend (FpDevice *dev)
{
  fpi_device_suspend_complete (dev, NULL);
}

static void
dev_resume (FpDevice *dev)
{
  fpi_device_resume_complete (dev, NULL);
}

static void
fpi_device_egis_et713_finalize (GObject *obj)
{
  FpiDeviceEgisEt713 *self = FPI_DEVICE_EGIS_ET713 (obj);

  g_free (self->path);
  g_clear_pointer (&self->ctx, g_main_context_unref);
  g_clear_object (&self->in);
  g_clear_object (&self->conn);
  G_OBJECT_CLASS (fpi_device_egis_et713_parent_class)->finalize (obj);
}

static void
fpi_device_egis_et713_init (FpiDeviceEgisEt713 *self)
{
}

static void
fpi_device_egis_et713_class_init (FpiDeviceEgisEt713Class *klass)
{
  FpDeviceClass *dev_class = FP_DEVICE_CLASS (klass);

  G_OBJECT_CLASS (klass)->finalize = fpi_device_egis_et713_finalize;
  dev_class->id = FP_COMPONENT;
  dev_class->full_name = "Egistec ET713 in-display fingerprint sensor (LG G8x)";
  dev_class->type = FP_DEVICE_TYPE_VIRTUAL;
  dev_class->id_table = id_table;
  dev_class->scan_type = FP_SCAN_TYPE_PRESS;
  dev_class->nr_enroll_stages = ENROLL_STAGES;
  dev_class->temp_hot_seconds = -1;

  dev_class->open = dev_open;
  dev_class->close = dev_close;
  dev_class->enroll = dev_enroll;
  dev_class->verify = dev_identify;
  dev_class->identify = dev_identify;
  dev_class->list = dev_list;
  dev_class->delete = dev_delete;
  dev_class->cancel = dev_cancel;
  dev_class->suspend = dev_suspend;
  dev_class->resume = dev_resume;

  fpi_device_class_auto_initialize_features (dev_class);
}
