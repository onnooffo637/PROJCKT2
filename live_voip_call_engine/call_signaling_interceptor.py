"""

Call Signaling Interceptor & Video-Call Blocker (Project Aether-Human V4.0)

Manages incoming VoIP call signaling:

- Smart Video-Call Blocker: Rejects video calls after 2-4s natural ring with realistic human excuse.

- Voice Screening: Prioritizes The Sovereign King (drops any ongoing call to answer the King),

  evaluates affinity for other callers, and simulates sleepy voice during circadian night.

"""



from __future__ import annotations



import asyncio

import logging

import random

import time

from typing import Any, Dict, Optional



from aether_human_core.config.settings import settings

from core_config.sovereignty_rules import sovereignty_guard

from aether_human_core.psychology_engine.circadian_rhythm import circadian_engine



logger = logging.getLogger("Aether.VoIP.SignalingInterceptor")





class CallSignalingInterceptor:

    """

    Intelligent signaling layer for VoIP voice & video calls.

    """



    VIDEO_EXCUSES = [

        "قافل كاميرا ليه يعم أنا قاعد في الضلمة ومتبهدل، رن صوت بس! 😂📞",

        "يا سيدي مش لابس حاجة معدولة وشعري منكوش، رن صوت ونتكلم براحتنا! 😅",

        "النت عندي ضعيف مبيستحملش فيديو، كلمني صوت أحسن وأوضح 📶",

        "قاعد وسط دوشة ومش جاهز أفتح كاميرا خالص دلوقتي، رن صوت يا غالي 🙏",

        "معلش مش بحب أفتح فيديو كول فجأة كده، كلمني مكالمة عادية وسامعك علطول!",

    ]



    SLEEPY_VOICE_RESPONSES = [

        "ألو... مين معايا... أنا كنت غرقان في النوم والله... خير فيه إيه؟ 🥱",

        "ألو... الساعة كام عندك يا عم... حد يرن على حد دلوقتي؟ بس قولي فيه حاجة مهمة؟",

        "ألووو... مش قادر أفتح عيني... ثانية بس أصحصح... أيوة معاك يا صاحبي...",

    ]



    BUSY_VOICE_TEXT_EXCUSES = [
        "مش فاضي أرد دلوقتي بعمل حاجة ابعت كتابة",
        "إيدي مشغولة دلوقتي مش هعرف أرد كول اكتبلي هنا عايز إيه",
        "قاعد في دوشة ومش هعرف أتكلم مكالمة دلوقتي ابعت مسدج",
        "معلش ورايا حاجة بخلصها دلوقتي ابعتلي كتابة وهشوفها",
    ]

    SPAM_CALL_TEXT_EXCUSES = [
        "بطل رن كتير يسطا أنا مش فاضي دلوقتي لو في حاجة مهمة اكتبها",
        "يا عم شفت رنتك والله بس مشغول دلوقتي ابعت كتابة",
    ]

    def __init__(self):
        self.active_call_user_id: Optional[int] = None
        self.active_call_start_time: float = 0.0
        # Task 2.3: Track per-caller recent call timestamps for spam detection
        self._caller_call_timestamps: Dict[int, list[float]] = {}

    async def evaluate_selective_voip_decision(
        self,
        caller_id: int,
        caller_name: str,
    ) -> Dict[str, Any]:
        """
        Task 2.3 (1) — Mood-Based Selective VoIP Call Answering:
        - Creator (ECENN / KING_USER_ID) -> Always answer immediately!
        - Other users -> Check caller relationship score, call frequency, and current mood (Hormones):
          * Good mood + close friend -> Accept call.
          * Annoyed, busy, low energy, or stranger / spamming calls -> Either ignore (let it ring)
            or reject (PhoneCallDiscardReasonBusy) and optionally send a casual human text 30s later.
        """
        is_the_king = sovereignty_guard.is_the_king(caller_id) or (settings.the_king_user_id > 0 and caller_id == settings.the_king_user_id) or caller_id in settings.super_admin_ids_list
        if is_the_king:
            return {
                "should_answer": True,
                "reason": "CREATOR_ALWAYS_ANSWER",
            }

        now = time.time()
        history = [t for t in self._caller_call_timestamps.get(caller_id, []) if now - t < 600.0]
        history.append(now)
        self._caller_call_timestamps[caller_id] = history
        is_spamming_calls = len(history) >= 2

        # Fetch caller relationship score & tier from DB
        affinity_score = 0.0
        relationship_tier = "STRANGER"
        user_role = "USER"
        try:
            from aether_human_core.database.postgres.connection import db_manager
            from aether_human_core.database.postgres.repositories.user_repo import UserRepository
            async with db_manager.session() as sess:
                u_repo = UserRepository(sess)
                u_rec = await u_repo.get_by_telegram_id(caller_id)
                if u_rec:
                    affinity_score = float(u_rec.affinity_score or 0.0)
                    relationship_tier = str(u_rec.relationship_tier or "STRANGER")
                    user_role = str(u_rec.role or "USER")
        except Exception as db_err:
            logger.debug(f"VoIP affinity lookup fallback for [{caller_id}]: {db_err}")

        # Fetch current mood (Hormones) & circadian state
        from aether_human_core.psychology_engine.neuro_hormones import endocrine_engine
        hormones = endocrine_engine.get_current_state()
        circadian = circadian_engine.evaluate_circadian_state()

        is_annoyed_or_low_energy = (
            hormones.cortisol > 0.60
            or hormones.serotonin < 0.35
            or hormones.dopamine < 0.32
        )
        is_sleeping = bool(circadian.get("is_sleeping", False))

        # 1. Villain or negative affinity -> reject without friendly follow-up
        if user_role == "VILLAIN" or affinity_score < 0.0:
            return {
                "should_answer": False,
                "mode": "REJECT_BUSY",
                "reason": "VILLAIN_OR_NEGATIVE_AFFINITY",
                "send_delayed_dm": False,
                "is_spam": False,
            }

        # 2. Spamming calls -> reject with busy + send annoyed human text 30s later
        if is_spamming_calls:
            return {
                "should_answer": False,
                "mode": "REJECT_BUSY",
                "reason": "CALL_SPAM_DETECTED",
                "send_delayed_dm": True,
                "is_spam": True,
            }

        # 3. Sleeping -> only answer very high affinity partner, ignore others (let it ring out)
        if is_sleeping and affinity_score < 70.0:
            return {
                "should_answer": False,
                "mode": "IGNORE_RING_OUT",
                "reason": "SLEEPING_LOW_ENERGY",
                "send_delayed_dm": False,
                "is_spam": False,
            }

        # 4. Annoyed / busy / low energy mood -> decline unless top-tier close friend
        if is_annoyed_or_low_energy:
            if affinity_score >= 65.0 and random.random() < 0.45:
                return {"should_answer": True, "reason": "CLOSE_FRIEND_DESPITE_LOW_MOOD"}
            mode = "REJECT_BUSY" if random.random() < 0.70 else "IGNORE_RING_OUT"
            return {
                "should_answer": False,
                "mode": mode,
                "reason": f"BAD_MOOD_CORTISOL_{hormones.cortisol:.2f}_SEROTONIN_{hormones.serotonin:.2f}",
                "send_delayed_dm": True,
                "is_spam": False,
            }

        # 5. Stranger or low-affinity acquaintance (< 25) -> selective! 70% reject/ignore + text
        if affinity_score < 25.0:
            if random.random() < 0.70:
                mode = "REJECT_BUSY" if random.random() < 0.65 else "IGNORE_RING_OUT"
                return {
                    "should_answer": False,
                    "mode": mode,
                    "reason": f"STRANGER_SELECTIVE_SCREENING_AFFINITY_{affinity_score:.1f}",
                    "send_delayed_dm": True,
                    "is_spam": False,
                }

        # 6. Good mood & friend -> Accept call!
        return {
            "should_answer": True,
            "reason": f"GOOD_MOOD_FRIEND_AFFINITY_{affinity_score:.1f}",
        }

    async def _send_delayed_busy_dm(
        self,
        client: Any,
        caller_id: int,
        caller_name: str,
        delay_sec: float = 30.0,
        is_spam: bool = False,
    ) -> None:
        """
        Waits ~30 seconds after rejecting/ignoring a call and sends a casual human DM:
        'مش فاضي أرد دلوقتي بعمل حاجة، ابعت كتابة'
        """
        await asyncio.sleep(delay_sec)
        excuse = random.choice(self.SPAM_CALL_TEXT_EXCUSES if is_spam else self.BUSY_VOICE_TEXT_EXCUSES)
        try:
            from aether_human_core.telegram_client.mtproto_manager import mtproto_manager
            from aether_human_core.telegram_client.human_typer import human_typer
            bursts = human_typer.prepare_message_bursts(excuse)
            await mtproto_manager.dispatch_burst_messages(
                chat_id=caller_id,
                bursts=bursts,
                is_userbot=True,
                userbot_client=client,
            )
            logger.info(f"📵 [VoIP Delayed Busy DM] Sent follow-up text after {delay_sec:.0f}s to [{caller_name} ({caller_id})]: '{excuse}'")
        except Exception as exc:
            logger.debug(f"Fallback direct send for delayed busy DM: {exc}")
            try:
                if client:
                    await client.send_message(caller_id, excuse)
            except Exception:
                pass



    async def handle_incoming_call_request(

        self,

        caller_id: int,

        caller_name: str,

        is_video: bool = False,

    ) -> Dict[str, Any]:

        """

        Processes incoming call event and decides signaling outcome:

        ACCEPT, REJECT_VIDEO_WITH_EXCUSE, REJECT_STRANGER, SLEEPY_ANSWER

        """

        logger.info(f"Incoming VoIP request from [{caller_id} ({caller_name})] | is_video={is_video}")



        # 1. Video Call Blocker: Strict immediate rejection of camera/video

        if is_video:

            ring_delay = random.uniform(2.0, 4.0)

            logger.info(f"📹 Video call detected from [{caller_name}]. Simulating {ring_delay:.1f}s ring before rejection...")

            await asyncio.sleep(ring_delay)

            excuse = random.choice(self.VIDEO_EXCUSES)

            return {

                "action": "REJECT_VIDEO",

                "reason": "VIDEO_CALLS_PROHIBITED",

                "chat_message": excuse,

                "should_callback_audio": True,

            }



        # 2. Sovereign King Priority:

        is_the_king = sovereignty_guard.is_the_king(caller_id) or caller_id in settings.super_admin_ids_list

        if is_the_king:

            if self.active_call_user_id and self.active_call_user_id != caller_id:

                logger.warning(

                    f"👑 King is calling! Terminating active call with User [{self.active_call_user_id}] immediately!"

                )

                self.terminate_active_call()



            self.active_call_user_id = caller_id

            self.active_call_start_time = time.time()

            return {

                "action": "ACCEPT_IMMEDIATELY",

                "priority": "SOVEREIGN_KING",

                "tone": "reverent_and_respectful",

                "greeting": f"يا أهلاً وسهلاً بمليكنا الغالي {caller_name}! شرفتني والله، سامعك وتحت أمرك يا باشا.",

            }



        # 3. Check Circadian Sleep State:

        circadian = circadian_engine.evaluate_circadian_state()

        if circadian.get("is_sleeping", False):

            ring_delay = random.uniform(5.0, 9.0)

            await asyncio.sleep(ring_delay)

            sleepy_text = random.choice(self.SLEEPY_VOICE_RESPONSES)

            return {

                "action": "ACCEPT_SLEEPY",

                "tone": "drowsy_and_sleepy",

                "greeting": sleepy_text,

            }



        # 3.5 Task 2.3: Selective Mood & Relationship Screening for regular users
        selective = await self.evaluate_selective_voip_decision(caller_id, caller_name)
        if not selective.get("should_answer", True):
            excuse = random.choice(
                self.SPAM_CALL_TEXT_EXCUSES if selective.get("is_spam") else self.BUSY_VOICE_TEXT_EXCUSES
            )
            return {
                "action": selective.get("mode", "REJECT_BUSY"),
                "reason": selective.get("reason", "SELECTIVE_DECLINE"),
                "chat_message": excuse if selective.get("send_delayed_dm") else None,
                "delay_dm_sec": 30.0,
            }

        # 4. Standard Voice Call Acceptance for regular users

        self.active_call_user_id = caller_id

        self.active_call_start_time = time.time()

        ring_delay = random.uniform(2.5, 4.5)

        await asyncio.sleep(ring_delay)

        return {

            "action": "ACCEPT",

            "tone": "warm_and_friendly",

            "greeting": f"ألوو يا هلا يا {caller_name}! إزيك يا صاحبي عامل إيه؟",

        }



    def terminate_active_call(self) -> None:

        if self.active_call_user_id:

            logger.info(f"Call with User [{self.active_call_user_id}] concluded.")

            self.active_call_user_id = None

            self.active_call_start_time = 0.0



    async def handle_incoming_telethon_call(self, client: Any, call: Any) -> None:

        """

        Intercepts incoming raw MTProto VoIP phone calls on Telethon Userbot.

        - Video Call: Rings for 3s, rejects with Busy, sends authentic human excuse text.

        - Audio Call: Rings for 4s, ends with Missed/Busy, and immediately sends an authentic voice note follow-up!

        """

        import os

        from telethon import functions, types

        from admin_telemetry_and_archiver.live_event_streamer import live_event_streamer



        # Accurately resolve caller ID and callee ID

        admin_id = getattr(call, "admin_id", 0)

        participant_id = getattr(call, "participant_id", 0)

        try:

            me = await client.get_me()

            my_id = getattr(me, "id", 0)

            userbot_name = getattr(me, "first_name", "Gg") or "Gg"

        except Exception:

            my_id = 0

            userbot_name = "Gg"



        # In incoming call to userbot, admin_id is the caller; participant_id is the userbot itself.

        if admin_id and admin_id != my_id:

            caller_id = admin_id

        elif participant_id and participant_id != my_id:

            caller_id = participant_id

        else:

            caller_id = admin_id or participant_id



        # Resolve caller entity and display name

        try:

            caller_entity = await client.get_entity(caller_id)

            caller_name = getattr(caller_entity, "first_name", f"User {caller_id}") or f"User {caller_id}"

        except Exception:

            caller_name = f"User {caller_id}"



        is_video = bool(getattr(call, "video", False))

        call_id = getattr(call, "id", 0)

        access_hash = getattr(call, "access_hash", 0)

        peer = types.InputPhoneCall(id=call_id, access_hash=access_hash)



        logger.info(

            f"📞 Intercepted raw Telethon VoIP call: Caller [{caller_name} ({caller_id})] | Call ID [{call_id}] | is_video={is_video}"

        )



        # 1. Acknowledge ringing so the caller's phone hears standard ringing tones

        try:

            await client(functions.phone.ReceivedCallRequest(peer=peer))

        except Exception as ex:

            logger.debug(f"ReceivedCallRequest notice: {ex}")



        # Case 1: Video Call -> Ring 3 seconds, discard with busy, send human excuse to caller

        if is_video:

            await asyncio.sleep(3.0)

            try:

                await client(

                    functions.phone.DiscardCallRequest(

                        peer=peer,

                        duration=0,

                        reason=types.PhoneCallDiscardReasonBusy(),

                        connection_id=0,

                    )

                )

            except Exception as ex:

                logger.debug(f"DiscardCallRequest (video) notice: {ex}")



            excuse = random.choice(self.VIDEO_EXCUSES)

            try:

                target_entity = None

                try:

                    target_entity = await client.get_entity(caller_id)

                except Exception:

                    try:

                        target_entity = await client.get_input_entity(caller_id)

                    except Exception:

                        pass



                if target_entity:

                    await client.send_message(target_entity, excuse)

                else:

                    await client.send_message(caller_id, excuse)

                logger.info(f"Sent video call refusal excuse to [{caller_id}] via Userbot MTProto: '{excuse}'")

            except Exception as ex:

                logger.warning(f"Direct MTProto send_message notice: {ex}. Attempting dispatch via MTProtoManager...")

                try:

                    from aether_human_core.telegram_client.mtproto_manager import mtproto_manager

                    from aether_human_core.telegram_client.human_typer import human_typer

                    bursts = human_typer.prepare_message_bursts(excuse)

                    await mtproto_manager.dispatch_burst_messages(

                        chat_id=caller_id,

                        bursts=bursts,

                        is_userbot=True,

                        userbot_client=client,

                    )

                    logger.info(f"Sent video call refusal excuse via MTProtoManager to [{caller_id}].")

                except Exception as fb_ex:

                    logger.error(f"Failed fallback sending video excuse: {fb_ex}")



            await live_event_streamer.stream_voip_event(

                caller_name=caller_name,

                caller_id=caller_id,

                call_type="VIDEO",

                action="REJECTED_WITH_EXCUSE",

                summary=f"تم رفض مكالمة الفيديو بعد رنين 3 ثوانٍ وإرسال العذر البشري: {excuse}",

            )



        # Case 2: Audio Call -> Task 2.3 Selective Mood/Relationship Screening before accepting
        else:
            selective = await self.evaluate_selective_voip_decision(caller_id, caller_name)
            if not selective.get("should_answer", True):
                mode = selective.get("mode", "REJECT_BUSY")
                reason = selective.get("reason", "SELECTIVE_DECLINE")
                logger.info(
                    f"📵 [Selective VoIP Screening] Declining call [{call_id}] from [{caller_name} ({caller_id})] "
                    f"| Mode={mode} | Reason={reason}"
                )
                if mode == "REJECT_BUSY":
                    await asyncio.sleep(random.uniform(2.5, 5.0))
                    try:
                        await client(
                            functions.phone.DiscardCallRequest(
                                peer=peer,
                                duration=0,
                                reason=types.PhoneCallDiscardReasonBusy(),
                                connection_id=0,
                            )
                        )
                    except Exception as disc_err:
                        logger.debug(f"DiscardCallRequest (selective busy) notice: {disc_err}")
                else:
                    # IGNORE_RING_OUT: Do not accept, let it ring naturally
                    logger.info(f"🔔 [Selective VoIP Screening] Letting call [{call_id}] from [{caller_name}] ring out unanswered.")

                if selective.get("send_delayed_dm", True):
                    asyncio.create_task(
                        self._send_delayed_busy_dm(
                            client=client,
                            caller_id=caller_id,
                            caller_name=caller_name,
                            delay_sec=random.uniform(27.0, 34.0),
                            is_spam=bool(selective.get("is_spam", False)),
                        )
                    )

                await live_event_streamer.stream_voip_event(
                    caller_name=caller_name,
                    caller_id=caller_id,
                    call_type="AUDIO_CALL_SELECTIVE",
                    action=mode,
                    summary=f"تم تجاهل/رفض المكالمة انتقائياً ({reason}) وجدولة رسالة نصية بعد 30 ثانية.",
                )
                return

            # Simulate natural human answer delay (1.0 to 1.8 seconds)
            await asyncio.sleep(random.uniform(1.0, 1.8))
            try:
                await client(functions.phone.ReceivedCallRequest(peer=peer))
            except Exception as ex:
                logger.debug(f"ReceivedCallRequest notice: {ex}")

            try:
                dh = await client(functions.messages.GetDhConfigRequest(version=0, random_length=256))
                incoming_proto = getattr(call, "protocol", None)
                g_a_hash = getattr(call, "g_a_hash", None)

                from live_voip_call_engine.full_duplex_pipeline import full_duplex_pipeline

                g_b, protocol = await full_duplex_pipeline.prepare_incoming_call(
                    call_id=call_id,
                    caller_id=caller_id,
                    caller_name=caller_name,
                    bot_name=userbot_name,
                    client=client,
                    peer=peer,
                    dh_g=dh.g,
                    dh_p=dh.p,
                    dh_random=os.urandom(256),
                    g_a_hash=g_a_hash,
                    incoming_proto=incoming_proto,
                )

                accept_res = await client(
                    functions.phone.AcceptCallRequest(
                        peer=peer,
                        g_b=g_b,
                        protocol=protocol,
                    )
                )
                logger.info(f"✅ VoIP Call [{call_id}] accepted successfully via MTProto for caller [{caller_name}].")

                phone_call_obj = getattr(accept_res, "phone_call", None)
                if isinstance(phone_call_obj, types.PhoneCall):
                    await full_duplex_pipeline.handle_phone_call_connected(phone_call_obj, client)

                self.active_call_user_id = caller_id
                self.active_call_start_time = time.time()

            except Exception as accept_err:
                logger.error(f"Failed to accept VoIP call [{call_id}]: {accept_err}", exc_info=True)
                await live_event_streamer.stream_voip_event(
                    caller_name=caller_name,
                    caller_id=caller_id,
                    call_type="AUDIO_CALL_LIVE",
                    action="CALL_ACCEPT_FAILED",
                    summary=f"فشل قبول المكالمة الصوتية عبر MTProto: {accept_err}",
                )





call_interceptor = CallSignalingInterceptor()

call_signaling_interceptor = call_interceptor

