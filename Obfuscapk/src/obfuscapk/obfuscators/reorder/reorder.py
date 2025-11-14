#!/usr/bin/env python3

import logging
import random
import re
from typing import List

from obfuscapk import obfuscator_category
from obfuscapk import util
from obfuscapk.obfuscation import Obfuscation
from obfuscapk.exceptions import PluginExecutionError,SmaliParsingError

#데이터 저장 클래스(뒤섞일 smail 코드 블록인 smil_code를 저장)
class CodeBlock:
    def __init__(self, jump_id=0, smali_code=""):
        self.jump_id = jump_id
        self.smali_code = smali_code

    def add_smali_code_to_block(self, smali_code):
        self.smali_code += smali_code


class Reorder(obfuscator_category.ICodeObfuscator):
    def __init__(self):
        self.logger = logging.getLogger(
            "{0}.{1}".format(__name__, self.__class__.__name__)
        )
        super().__init__()

       #코드가 if 구문이면 리버싱을 어렵게 하기 위해서 조건 뒤집기
        self.if_mapping = {
            "if-eq": "if-ne", #같으면 => 같지 않으면
            "if-ne": "if-eq",
            "if-lt": "if-ge", #작으면 => 크거나 같으면
            "if-ge": "if-lt",
            "if-gt": "if-le",
            "if-le": "if-gt",
            "if-eqz": "if-nez",
            "if-nez": "if-eqz", #0과 같으면 => 0과 같지 않으면
            "if-ltz": "if-gez",
            "if-gez": "if-ltz",
            "if-gtz": "if-lez", #0보다 크면 => 0보다 작거나 같으면
            "if-lez": "if-gtz",
        }

    def obfuscate(self, obfuscation_info: Obfuscation):
        self.logger.info('Running "{0}" obfuscator'.format(self.__class__.__name__))
         #[고도화 1] smali_file 변수가 정의되지 않은 상태에서 예외가 발생할 수 있으므로 초기화
        smali_file = "unknown"
        try:
            #goto, if-eq 등 유효한 명령어 목록 op_cods에 저장
            op_codes = util.get_code_block_valid_op_codes()
            #smali 코드에서 명령어 부분(if-eq, const-string등을) 추출하기 위한 첫번째 정규식
            op_code_pattern = re.compile(r"\s+(?P<op_code>\S+)")
            #if 구문에서 레지스터(v0,v1 등)와 점프할 라벨(:labelA 등)을 추출하기 위한 두번째 정규식
            if_pattern = re.compile(
                r"\s+(?P<if_op_code>\S+)"
                r"\s(?P<register>[vp0-9,\s]+?),\s:(?P<goto_label>\S+)"
            )

             
            for smali_file in util.show_list_progress(
                obfuscation_info.get_smali_files(),
                interactive=obfuscation_info.interactive,
                description="Code reordering",
            ):
                self.logger.debug('Reordering code in file "{0}"'.format(smali_file))

                #PASS 1: 각 메소드 내부에서 유효한 명령어 앞에 점프 구문과 레이블을 삽입
                with util.inplace_edit_file(smali_file) as (in_file, out_file):
                    editing_method = False #현재 메소드 내부 편집 중인지 여부
                    inside_try_catch = False #현재 try-catch 블록 내부인지 여부
                    jump_count = 0  #삽입된 점프 구문의 고유 번호
                    for line in in_file:
                        if (
                            line.startswith(".method ") #매서드 시작 부분 감지
                            and " abstract " not in line
                            and " native " not in line
                            and not editing_method
                        ):
                            # If at the beginning of a non abstract/native method
                            out_file.write(line) #메소드 시작 라인 출력
                            editing_method = True   #메소드 내부 편집 상태로 전환
                            inside_try_catch = False #try-catch 블록 내부 상태 초기화
                            jump_count = 0 #점프 구문 카운트 초기화

                       #메서드 끝을 감지하고 상태 리셋
                        elif line.startswith(".end method") and editing_method:
                            # If a the end of the method.
                            out_file.write(line)
                            editing_method = False
                            inside_try_catch = False # 매서드가 끝났이 코드를 절대 수정 안하게 보장 

                        elif editing_method:
                            # Inside method. Check if this line contains an op code at
                            # the beginning of the string.
                            match = op_code_pattern.match(line)
                            if match:
                                op_code = match.group("op_code")

                                # Check if we are entering or leaving a try-catch
                                # block of code.
                                if op_code.startswith(":try_start_"):
                                    out_file.write(line)
                                    inside_try_catch = True
                                elif op_code.startswith(":try_end_"):
                                    out_file.write(line)
                                    inside_try_catch = False

                                # If this is a valid op code, and we are not inside a
                                # try-catch block, mark this section with a special
                                # label that will be used later and invert the if
                                # conditions (if any).
                                elif op_code in op_codes and not inside_try_catch: #유효한 명령어이고, try-catch안이 아니면(안전하게 수정 가능), try-catch 내부는 수정 X(민감한 부분이니)
                                    jump_name = util.get_random_string(16)
                                    out_file.write( #goto 구문과 레이블 삽입
                                        "\tgoto/32 :l_{label}_{count}\n\n".format(
                                            label=jump_name, count=jump_count
                                        )
                                    )
                                    out_file.write("\tnop\n\n")
                                    out_file.write("#!code_block!#\n") #PASS 2에서 코드 블록을 식별하기 위한 마커
                                    out_file.write( #goto 구문이 점프할 레이블 삽입(목적지 label)
                                        "\t:l_{label}_{count}\n".format(
                                            label=jump_name, count=jump_count
                                        )
                                    )
                                    jump_count += 1

                                    #현재 명령어가 if 구문인지 확인
                                    new_if = self.if_mapping.get(op_code, None)
                                    if new_if: #if 구문이라면
                                        if_match = if_pattern.match(line) #두번째 정규식으로 레지스터와 레이블 파싱
                                        #정규식으로 파싱을 실패하면 프로그램이 멈춤 => if_match객체가 None이 아닌 경우에만 실행하게 해야 함


                                        #[고도화 3] 정규식 파싱 실패에 대한 오류 처리
                                        if if_match:
                                            random_label_name = util.get_random_string(16)
                                            out_file.write( #if 구문 조건 뒤집기 및 점프 구문 삽입
                                                "\t{if_cond} {register}, "
                                                ":gl_{new_label}\n\n".format(
                                                      if_cond=new_if,
                                                      register=if_match.group("register"),
                                                      new_label=random_label_name,
                                                )
                                            )       
                                            out_file.write( #원래 점프 레이블로 이동하는 goto 구문 삽입
                                                "\tgoto/32 :{0}\n\n".format(
                                                if_match.group("goto_label")
                                                )
                                            )
                                            out_file.write(
                                                "\t:gl_{0}".format(random_label_name)
                                            )
                                        else: #정규식 파싱 실패 시
                                            #프로그램을 죽이지 말고, 경고 로그 남기고 원본 라인을 쓴다
                                            self.logger.warning(
                                               f"Could not parse 'if' statement in file '{smali_file}'. "
                                               f"Skipping line: {line.strip()}"
                                               
                                            )
                                            out_file.write(line)    


                                    else: #if 구문이 아니면 원본 라인 출력
                                          out_file.write(line)
                                else:
                                    out_file.write(line)
                            else:
                                out_file.write(line)

                        else:
                            out_file.write(line)

                # Reorder code blocks randomly.
                # PASS 2: 각 메소드 내부에서 마커로 표시된 코드 블록들을 무작위로 뒤섞기
                with util.inplace_edit_file(smali_file) as (in_file, out_file):
                    editing_method = False
                    block_count = 0
                    code_blocks: List[CodeBlock] = [] #코드 블록 리스트
                    current_code_block = None #현재 Smail 코드 블록
                    for line in in_file:
                        if (
                            line.startswith(".method ")
                            and " abstract " not in line
                            and " native " not in line
                            and not editing_method
                        ):
                            # If at the beginning of a non abstract/native method
                            out_file.write(line)
                            editing_method = True
                            block_count = 0
                            code_blocks = []
                            current_code_block = None

                        elif line.startswith(".end method") and editing_method: #매소드 끝을 만나면
                            # If a the end of the method.
                            editing_method = False
                            random.shuffle(code_blocks) #코드 블록 무작위로 뒤섞기
                            for code_block in code_blocks: #뒤섞인 코드 블록 다시 파일에 쓰기
                                out_file.write(code_block.smali_code)
                            out_file.write(line)

                        elif editing_method:
                            # Inside method. Check if this line is marked with
                            # a special label.
                            if line.startswith("#!code_block!#"): #마커 발견 시 새로운 코드 블록 시작
                                block_count += 1
                                current_code_block = CodeBlock(block_count, "") #새로운 객체 생성해서 추가
                                code_blocks.append(current_code_block)
                            else:
                                if block_count > 0 and current_code_block:
                                    current_code_block.add_smali_code_to_block(line)
                                else:
                                    out_file.write(line)

                        else:
                            out_file.write(line)

       #[고도화 1] Smail 파싱 실패(AttributeError 등)로 인한 오류 처리
        except AttributeError as e:
            self.logger.error(
                'Error during execution of "{0}" obfuscator: Smail parsing failed: {1}'.format(
                    self.__class__.__name__, e
                )
            )
            #AttributeError는 SmailParsingError로 래핑해서 상위 모듈에 전달
            raise SmaliParsingError(
                plugin_name=self.__class__.__name__,
                file_path=smali_file,
                details=str(e)
            ) from e



       #[고도화 2] 그 외에 모든 일반적인 오류
        except Exception as e:
            self.logger.error(
                'Error during execution of "{0}" obfuscator: {1}'.format(
                    self.__class__.__name__, e
                )
            )
            raise PluginExecutionError(
                plugin_name=self.__class__.__name__,
                details=str(e)
            ) from e

        finally:
            obfuscation_info.used_obfuscators.append(self.__class__.__name__)
