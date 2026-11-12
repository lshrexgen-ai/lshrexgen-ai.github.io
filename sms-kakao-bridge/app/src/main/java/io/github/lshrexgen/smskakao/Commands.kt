package io.github.lshrexgen.smskakao

import android.content.Context

/**
 * Interprets a message typed into the KakaoTalk console room.
 *
 *   @01012345678 내용   -> SMS to that number
 *   @홍길동 내용         -> SMS to the first contact matching the name
 *   내용                -> SMS to the last SMS sender (when enabled)
 *   /도움, /help        -> usage
 *   /최근, /last        -> show the last sender
 */
object Commands {
    private const val HELP = """사용법
@번호 내용 → 그 번호로 문자
@이름 내용 → 연락처 이름으로 문자
내용만 입력 → 마지막 문자 발신자에게 답장
/최근 → 마지막 발신자 확인"""

    fun handle(ctx: Context, sender: String, raw: String) {
        val text = raw.trim()
        if (text.isEmpty()) return
        val prefs = Prefs.get(ctx)

        when (text.lowercase()) {
            "/도움", "/help", "/?" -> { KakaoBridge.send(ctx, HELP); return }
            "/최근", "/last" -> {
                val last = prefs.lastSender
                KakaoBridge.send(ctx, if (last.isEmpty()) "아직 받은 문자가 없습니다" else "마지막 발신자: $last")
                return
            }
        }

        val number: String
        val body: String
        if (text.startsWith("@")) {
            val sp = text.indexOfFirst { it.isWhitespace() }
            if (sp < 0) { KakaoBridge.send(ctx, "보낼 내용이 없습니다\n$HELP"); return }
            val who = text.substring(1, sp).trim()
            body = text.substring(sp + 1).trim()
            number = if (SmsSender.looksLikeNumber(who)) {
                SmsSender.normalize(who)
            } else {
                Contacts.numberFor(ctx, who) ?: run {
                    KakaoBridge.send(ctx, "연락처에서 '$who'를 찾지 못했습니다")
                    return
                }
            }
        } else {
            if (!prefs.replyToLast) { KakaoBridge.send(ctx, "@번호 로 시작해 주세요\n$HELP"); return }
            number = prefs.lastSender
            if (number.isEmpty()) { KakaoBridge.send(ctx, "아직 받은 문자가 없어 답장할 상대가 없습니다"); return }
            body = text
        }

        try {
            SmsSender.send(ctx, number, body)
            EventLog.add("문자 발송: $number (${body.length}자)")
            if (prefs.sendAck) {
                val name = if (prefs.lookupContacts) Contacts.nameFor(ctx, number) else null
                KakaoBridge.send(ctx, "✅ 전송 → ${name?.let { "$it ($number)" } ?: number}")
            }
        } catch (e: Exception) {
            EventLog.add("문자 발송 실패: $number: ${e.message}")
            KakaoBridge.send(ctx, "❌ 전송 실패 ($number): ${e.message}")
        }
    }
}
