# Supabase 탈퇴 정리 함수 및 한국시간 자정 Cron 작업 멱등 적용

import asyncio

from sqlalchemy import text

from backend.core.config import settings
from backend.core.database import engine


JOB_NAME = "purge-withdrawn-users-midnight-kst"  # Supabase에서 중복 없이 갱신할 Cron 작업명
SCHEDULE_UTC = "0 15 * * *"  # 한국시간 자정에 해당하는 UTC 전날 15시
GRACE_DAYS = settings.withdrawal_grace_days  # 탈퇴 취소 가능 기간
PURGE_DAYS = GRACE_DAYS + settings.withdrawal_retention_days  # 탈퇴 접수부터 최종 삭제까지 기간


# 반복 실행에도 하나만 유지되는 탈퇴 정리 함수 및 자정 Cron
async def run() -> None:
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS pg_cron"))
        await connection.execute(
            text(
                f"""
                CREATE OR REPLACE FUNCTION public.purge_withdrawn_users()
                RETURNS JSONB
                LANGUAGE plpgsql
                SECURITY DEFINER
                SET search_path = public
                AS $function$
                DECLARE
                  transitioned_count INTEGER;
                  deleted_count INTEGER;
                BEGIN
                  UPDATE public.users
                  SET status = 'withdrawn'
                  WHERE status = 'pending_deletion'
                    AND withdrawn_at <= NOW() - INTERVAL '{GRACE_DAYS} days';
                  GET DIAGNOSTICS transitioned_count = ROW_COUNT;

                  DELETE FROM public.users
                  WHERE status = 'withdrawn'
                    AND withdrawn_at <= NOW() - INTERVAL '{PURGE_DAYS} days';
                  GET DIAGNOSTICS deleted_count = ROW_COUNT;

                  RETURN jsonb_build_object(
                    'transitioned', transitioned_count,
                    'deleted', deleted_count,
                    'executed_at', NOW()
                  );
                END;
                $function$
                """
            )
        )
        await connection.execute(
            text("REVOKE ALL ON FUNCTION public.purge_withdrawn_users() FROM PUBLIC")
        )
        await connection.execute(
            text("GRANT EXECUTE ON FUNCTION public.purge_withdrawn_users() TO postgres")
        )

        existing_job_ids = (
            await connection.execute(
                text("SELECT jobid FROM cron.job WHERE jobname = :job_name"),
                {"job_name": JOB_NAME},
            )
        ).scalars().all()
        for job_id in existing_job_ids:
            await connection.execute(text("SELECT cron.unschedule(:job_id)"), {"job_id": job_id})

        await connection.execute(
            text("SELECT cron.schedule(:job_name, :schedule, :command)"),
            {
                "job_name": JOB_NAME,
                "schedule": SCHEDULE_UTC,
                "command": "SELECT public.purge_withdrawn_users()",
            },
        )

    print(
        f"cron_job={JOB_NAME}, schedule_utc={SCHEDULE_UTC}, schedule_kst=00:00, "
        f"grace_days={GRACE_DAYS}, purge_days={PURGE_DAYS}"
    )


if __name__ == "__main__":
    asyncio.run(run())
