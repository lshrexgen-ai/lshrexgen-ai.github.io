// Gmail 일정 요청 메일 -> Google Calendar 자동 등록
// Script Properties: ANTHROPIC_API_KEY (필수), CALENDAR_ID (기본 rexgenshlee@gmail.com)

var PROCESSED_LABEL = 'cal-processed';
var KEYWORDS = '(일정 OR 미팅 OR 회의 OR 약속 OR 방문 OR 면담 OR 심의 OR 세미나 OR meeting OR invite OR appointment OR schedule)';
var MODEL = 'claude-haiku-5-5';

function processInbox() {
  var props = PropertiesService.getScriptProperties();
  var calId = props.getProperty('CALENDAR_ID') || 'rexgenshlee@gmail.com';
  var cal = CalendarApp.getCalendarById(calId);
  if (!cal) throw new Error('캘린더를 찾을 수 없습니다: ' + calId + ' (공유/권한 확인)');

  var label = GmailApp.getUserLabelByName(PROCESSED_LABEL) || GmailApp.createLabel(PROCESSED_LABEL);
  var threads = GmailApp.search('in:inbox newer_than:2d -label:' + PROCESSED_LABEL + ' ' + KEYWORDS, 0, 20);

  threads.forEach(function (thread) {
    try {
      var msg = thread.getMessages().pop();
      var info = extractEvent_(msg);
      if (info && info.is_event && info.start) {
        createEvent_(cal, info, msg);
      }
      thread.addLabel(label); // 일정이 아니어도 재처리 방지
    } catch (e) {
      console.error(thread.getFirstMessageSubject() + ': ' + e);
    }
  });
}

function extractEvent_(msg) {
  var key = PropertiesService.getScriptProperties().getProperty('ANTHROPIC_API_KEY');
  if (!key) throw new Error('ANTHROPIC_API_KEY 미설정');

  var today = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd (E)');
  var prompt =
    '오늘은 ' + today + ' (Asia/Seoul)입니다. 아래 이메일이 일정/약속/회의 요청이면 JSON만 출력하세요.\n' +
    '{"is_event":bool,"title":str,"start":"YYYY-MM-DDTHH:mm:ss","end":"YYYY-MM-DDTHH:mm:ss"|null,' +
    '"all_day":bool,"location":str|null,"description":str,"confidence":0~1}\n' +
    '일정이 아니거나 날짜를 알 수 없으면 {"is_event":false}. 종료시간이 없으면 end는 null.\n\n' +
    '보낸사람: ' + msg.getFrom() + '\n제목: ' + msg.getSubject() + '\n본문:\n' +
    msg.getPlainBody().substring(0, 4000);

  var res = UrlFetchApp.fetch('https://api.anthropic.com/v1/messages', {
    method: 'post',
    contentType: 'application/json',
    headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01' },
    payload: JSON.stringify({
      model: MODEL,
      max_tokens: 500,
      messages: [{ role: 'user', content: prompt }]
    }),
    muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) throw new Error('API ' + res.getResponseCode() + ' ' + res.getContentText());

  var text = JSON.parse(res.getContentText()).content[0].text;
  var m = text.match(/\{[\s\S]*\}/);
  return m ? JSON.parse(m[0]) : null;
}

function createEvent_(cal, info, msg) {
  var uncertain = (info.confidence || 0) < 0.7;
  var title = (uncertain ? '[확인필요] ' : '') + info.title;
  var desc = info.description + '\n\n원본 메일: ' + msg.getSubject() + ' / ' + msg.getFrom() +
    '\nhttps://mail.google.com/mail/u/0/#inbox/' + msg.getThread().getId();
  var opts = { description: desc };
  if (info.location) opts.location = info.location;

  var start = new Date(info.start);
  var ev;
  if (info.all_day) {
    ev = cal.createAllDayEvent(title, start, opts);
  } else {
    var end = info.end ? new Date(info.end) : new Date(start.getTime() + 60 * 60 * 1000);
    ev = cal.createEvent(title, start, end, opts);
  }
  if (uncertain) ev.setColor(CalendarApp.EventColor.ORANGE);
}

// 한 번만 실행: 5분 간격 트리거 등록
function installTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) { ScriptApp.deleteTrigger(t); });
  ScriptApp.newTrigger('processInbox').timeBased().everyMinutes(5).create();
}
