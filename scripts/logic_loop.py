# -*- coding: utf-8 -*-
import json
import time
import datetime
from pathlib import Path
from utils.print_log import print, logger
from utils.random_utils import random_min_max

class LoopMixin:
    """메인 실행 루프 및 반복 상태 관리를 담당하는 Mixin"""

    def _maybe_export_db_xlsx(self, force: bool = False):
        """설정된 간격에 따라 DB를 엑셀 파일로 내보냅니다."""
        if force:
            self.db.json_to_xlsx()
            return

        interval = self.get_config('json_to_xlsx_interval', 0)
        if interval and hasattr(self, '_xlsx_export_counter'):
            self._xlsx_export_counter += 1
            if self._xlsx_export_counter >= interval:
                self.db.json_to_xlsx()
                self._xlsx_export_counter = 0

    def run(self):
        """자동화 프로세스의 엔트리 포인트"""
        try:
            self.init(db=True)
            self.start_observers()
            
            while True:
                try:
                    self._loop()
                except Exception:
                    logger.exception('Exception in main loop')
                    print.exception(show_locals=True)
            
        except KeyboardInterrupt:
            print.Warn('사용자에 의해 중단되었습니다 (KeyboardInterrupt)')
            logger.info('KeyboardInterrupt')
        except Exception:
            logger.exception('Critical error in automation run')
            print.exception(show_locals=True)
        finally:
            # 종료 전 리소스 정리
            self.stop_observers()
            self.db.close()
            self._maybe_export_db_xlsx(force=True)
            print.save_html()
            print.Info(' === ComfyUI Automation Finished === ')

    def _loop(self):
        """개별 이미지 생성을 위한 단일 루프 단위"""
        if self.get_config('수정 안해서 작동 안시킴', False):
            print.Warn('config.yml의 "수정 안해서 작동 안시킴" 항목이 True입니다. 5초 대기...')
            time.sleep(5)
            return
        
        self.lora_num = 0
        
        # 1. 체크포인트 변경 주기 판단
        if self.checkpoint_loop_cnt == 0:
            self._maybe_export_db_xlsx()
            self.checkpoint_change()
            self.checkpoint_loop_cnt += 1
            self.char_loop_cnt = 0

        # 워크플로우 템플릿 복사
        # if not self.fromImg:
        self.copy_workflow_api()
        
        # 2. 캐릭터 변경 주기 판단
        if self.char_loop_cnt == 0:
            self.char_change()
            self.char_loop_cnt += 1
            self.queue_loop_cnt = 0
        
        # 3. LoRA 변경 주기 판단
        if self.queue_loop_cnt == 0:
            self.lora_change()
            self.queue_loop_cnt += 1
     
        # 4. 워크플로우 노드 값 설정
        self.set_setup_workflow_to_workflow_api()
        self.set_checkpoint_loader_simple()
        self.set_ksampler()
        self.set_dic_checkpoint_yml_to_workflow_api()
        self.set_char()
        self.set_lora()
        self.set_seed()
        self.set_wildcard()
    
        self._sync_model_names(self.workflow_api)
        self.set_save_image()
        
        # 로깅 및 디버그 정보 출력
        if self.get_config("WorkflowPrint", False):
            print.Config('workflow_api', self.workflow_api)        
            logger.debug(f"Workflow API: {self.workflow_api}")    
        
        if self.get_config("WorkflowSave", False):
            with open("log/" + self.prefix_name + ".json", "w", encoding="utf-8") as f:
                json.dump(self.workflow_api, f, indent=2, ensure_ascii=False)


        # 루프 한계값 동적 로드 (숫자 또는 리스트 기반 랜덤)
        self.checkpoint_loop = random_min_max(self.get_config("CheckpointLoop", 1))
        self.char_loop = random_min_max(self.get_config("CharLoop", 1))
        self.queue_loop = random_min_max(self.get_config("queueLoop", 1))
        
        self.total += 1
        elapsed = datetime.timedelta(seconds=(time.time() - self.time_start))
        
        print(f"{self.total} {self.checkpoint_loop_cnt}/{self.checkpoint_loop} "
              f"{self.char_loop_cnt}/{self.char_loop} {self.queue_loop_cnt}/{self.queue_loop} "
              f"{elapsed} {self.checkpoint_name} {self.char_name}")
        
        # DB 기록 업데이트
        if not self.fromImg:
            self.db.update(
                self.checkpoint_type, self.checkpoint_name, self.char_name, self.loras_set,
                tags=self._collect_lora_tags()
            )
        
        # 5. ComfyUI 전송
        success, status_code = self._queue()
        
        # fromImg 모드 에러 핸들링
        if not success and self.fromImg and status_code == 400:
            failed_img = self.from_img_path
            self.from_img_path = self._select_from_img(exclude={failed_img})
            if not self.from_img_path:
                self.checkpoint_kind = 'Weight'
            return
        
        time.sleep(random_min_max(self.get_config("sleep", 1)))
        
        # 6. 카운터 업데이트 및 루프 전이
        self.queue_loop_cnt += 1
        if self.queue_loop_cnt > self.queue_loop:
            self.queue_loop_cnt = 0
            self.char_loop_cnt += 1
        
        if self.char_loop_cnt > self.char_loop:
            self.char_loop_cnt = 0
            self.checkpoint_loop_cnt += 1
        
        if self.checkpoint_loop_cnt > self.checkpoint_loop:
            self.checkpoint_loop_cnt = 0