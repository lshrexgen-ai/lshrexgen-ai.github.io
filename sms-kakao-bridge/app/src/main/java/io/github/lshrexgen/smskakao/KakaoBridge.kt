package io.github.lshrexgen.smskakao

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.RemoteInput
import android.content.Context
import android.content.Intent
import android.os.Bundle
import java.util.ArrayDeque

/**
 * Sends text into the configured KakaoTalk room by re-using the "reply" RemoteInput action
 * of the most recent notification KakaoTalk posted for that room.
 *
 * KakaoTalk has no public "send message" API, so until the bot account has received at least one
 * message from the room (which produces a notification), outgoing text is queued.
 */
object KakaoBridge {
    const val KAKAO_PACKAGE = "com.kakao.talk"
    private const val CHANNEL_ID = "bridge"
    private const val NOTIF_NEED_PING = 2

    class ReplyTarget(val action: Notification.Action, val remoteInput: RemoteInput, val userId: Int)

    @Volatile private var target: ReplyTarget? = null
    private val queue = ArrayDeque<String>()
    @Volatile private var loaded = false

    /** Restore the outgoing queue saved before the process was killed. */
    private fun load(ctx: Context) {
        if (loaded) return
        synchronized(queue) {
            if (loaded) return
            val raw = Prefs.get(ctx).pendingQueue
            if (raw.isNotEmpty()) runCatching {
                val arr = org.json.JSONArray(raw)
                for (i in 0 until arr.length()) queue.addLast(arr.getString(i))
            }
            loaded = true
            if (queue.isNotEmpty()) EventLog.add("대기 중인 카톡 메시지 ${queue.size}건 복원")
        }
    }

    private fun persist(ctx: Context) {
        val json = synchronized(queue) { org.json.JSONArray(queue.toList()).toString() }
        Prefs.get(ctx).pendingQueue = if (json == "[]") "" else json
    }

    val pendingCount: Int get() = synchronized(queue) { queue.size }

    val hasTarget: Boolean get() = target != null

    /** Called by the notification listener whenever a notification for the console room arrives. */
    fun updateTarget(ctx: Context, notification: Notification, userId: Int, flush: Boolean = true) {
        val action = notification.actions?.firstOrNull { a -> a.remoteInputs?.isNotEmpty() == true } ?: return
        val ri = action.remoteInputs.first()
        val first = target == null
        target = ReplyTarget(action, ri, userId)
        if (first) EventLog.add("카톡 답장 경로 확보 (user $userId)")
        if (flush) flush(ctx)
    }

    /** Queue [text] for the room and try to send immediately. */
    fun send(ctx: Context, text: String) {
        load(ctx)
        synchronized(queue) { queue.addLast(text) }
        persist(ctx)
        flush(ctx)
    }

    /** Send directly, bypassing the queue. Returns false when no reply action is cached yet. */
    fun sendNow(ctx: Context, text: String): Boolean {
        if (target == null) KakaoNotificationListener.recoverTarget()
        val t = target ?: return false
        return try {
            val intent = Intent()
            val results = Bundle().apply { putCharSequence(t.remoteInput.resultKey, text) }
            RemoteInput.addResultsToIntent(arrayOf(t.remoteInput), intent, results)
            t.action.actionIntent.send(ctx, 0, intent)
            true
        } catch (e: PendingIntent.CanceledException) {
            EventLog.add("카톡 답장 경로 만료됨: 봇 계정으로 아무 메시지나 다시 보내 주세요")
            target = null
            false
        } catch (e: Exception) {
            EventLog.add("카톡 전송 실패: ${e.message}")
            false
        }
    }

    fun flush(ctx: Context) {
        load(ctx)
        if (target == null) KakaoNotificationListener.recoverTarget()
        if (target == null) {
            val n = synchronized(queue) { queue.size }
            if (n > 0) notifyNeedPing(ctx, n)
            return
        }
        while (true) {
            val next = synchronized(queue) { queue.peekFirst() } ?: break
            if (!sendNow(ctx, next)) break
            synchronized(queue) { queue.pollFirst() }
            persist(ctx)
            EventLog.add("카톡 전송: ${next.lineSequence().first().take(40)}")
        }
        if (synchronized(queue) { queue.isEmpty() }) {
            (ctx.getSystemService(NotificationManager::class.java)).cancel(NOTIF_NEED_PING)
        }
    }

    fun ensureChannel(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL_ID) == null) {
            nm.createNotificationChannel(
                NotificationChannel(CHANNEL_ID, "SMS-카톡 브리지", NotificationManager.IMPORTANCE_DEFAULT)
            )
        }
    }

    private fun notifyNeedPing(ctx: Context, pending: Int) {
        ensureChannel(ctx)
        val pi = PendingIntent.getActivity(
            ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE,
        )
        val n = Notification.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.stat_notify_chat)
            .setContentTitle("카톡 답장 경로가 아직 없습니다")
            .setContentText("봇 카톡에 아무 메시지나 보내면 대기 중인 문자 ${pending}건을 전달합니다")
            .setContentIntent(pi)
            .setAutoCancel(true)
            .build()
        ctx.getSystemService(NotificationManager::class.java).notify(NOTIF_NEED_PING, n)
    }

    fun channelId() = CHANNEL_ID
}
