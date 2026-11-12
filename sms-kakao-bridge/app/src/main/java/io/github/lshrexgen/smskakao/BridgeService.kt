package io.github.lshrexgen.smskakao

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder

/** Lightweight foreground service so Samsung's battery manager keeps the process alive. */
class BridgeService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        KakaoBridge.ensureChannel(this)
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
        )
        val n = Notification.Builder(this, KakaoBridge.channelId())
            .setSmallIcon(android.R.drawable.stat_notify_sync_noanim)
            .setContentTitle("SMS ↔ 카톡 브리지 실행 중")
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
        startForeground(1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE)
        return START_STICKY
    }

    companion object {
        fun start(ctx: Context) {
            runCatching { ctx.startForegroundService(Intent(ctx, BridgeService::class.java)) }
                .onFailure { EventLog.add("서비스 시작 실패: ${it.message}") }
        }
    }
}
