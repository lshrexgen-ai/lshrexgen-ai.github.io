package io.github.lshrexgen.smskakao

import android.content.Context
import android.telephony.SmsManager

object SmsSender {
    /** Keep digits and a leading '+'. "010-1234-5678" -> "01012345678". */
    fun normalize(raw: String): String {
        val digits = raw.filter { it.isDigit() }
        return if (raw.trim().startsWith("+")) "+$digits" else digits
    }

    fun looksLikeNumber(s: String): Boolean {
        val n = normalize(s)
        return n.length >= 3 && s.all { it.isDigit() || it in "+-() " }
    }

    /** Sends [body] to [number] as a (multipart) text message. Throws on failure. */
    fun send(ctx: Context, number: String, body: String) {
        require(body.isNotBlank()) { "빈 메시지" }
        val sm = ctx.getSystemService(SmsManager::class.java)
            ?: throw IllegalStateException("SmsManager 없음")
        val parts = sm.divideMessage(body)
        if (parts.size == 1) {
            sm.sendTextMessage(number, null, body, null, null)
        } else {
            sm.sendMultipartTextMessage(number, null, parts, null, null)
        }
    }
}
