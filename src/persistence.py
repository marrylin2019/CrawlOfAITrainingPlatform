from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from . import DB_PATH, STATUS_MAP


class DDL:
    ENGINE = create_engine(f'sqlite:///{DB_PATH}', echo=False)
    __Base = declarative_base()

    def __init__(self):
        self.__Tables = self.__create_tables()

    @property
    def Tables(self):
        return self.__Tables

    def __create_tables(self):
        tables = {
            'Users': self.__reg_users(),
            'Tasks': self.__reg_tasks(),
            'Configs': self.__reg_configs()
        }
        self.__Base.metadata.create_all(self.ENGINE)
        return tables

    def __reg_users(self):
        BASE = self.__Base

        class Users(BASE):
            __tablename__ = 'users'
            id = Column(Integer, primary_key=True, autoincrement=True)
            account = Column(String(50), nullable=False)
            password = Column(String(50), nullable=False)
            token = Column(String(50), nullable=True)
            # userId，用户id
            user_id = Column(String, nullable=True)
            # phone，手机号
            phone = Column(String, nullable=True)

            tasks = relationship('Tasks', back_populates='user')

            def to_dict(self) -> dict:
                for col_key in self.__table__.columns.keys():
                    if col_key in ['password', 'token']:
                        setattr(self, col_key, '******')
                return {col_key: getattr(self, col_key) for col_key in self.__table__.columns.keys()}

        return Users

    def __reg_tasks(self):
        BASE = self.__Base

        class Tasks(BASE):
            __tablename__ = 'tasks'
            # id，任务id，可用于开关机
            id = Column(String, primary_key=True)
            # taskName，任务名称，一定程度上反映任务创建时间
            name = Column(String, nullable=False)
            # status，机器状态码，取值1-14
            # __status = Column(String, nullable=False)
            status = Column(String, nullable=False)
            # releaseTime，释放时间
            release_time = Column(String, nullable=True)
            # updateTime，最后更新时间
            update_time = Column(String, nullable=False)
            # agentIp，代理ip
            agent_ip = Column(String, nullable=False)
            # sshPort，ssh端口
            ssh_port = Column(String, nullable=False)
            # sshPasswd，ssh密码
            ssh_passwd = Column(String, nullable=False)
            # jupyterPort，jupyter端口
            jupyter_port = Column(String, nullable=False)
            # jupyterPasswd，jupyter密码
            jupyter_passwd = Column(String, nullable=False)
            # vncPort，vnc端口
            vnc_port = Column(String, nullable=False)
            # vncPasswd，vnc密码
            vnc_passwd = Column(String, nullable=False)
            # vscodePort，vscode端口
            vscode_port = Column(String, nullable=False)
            # vscodePasswd，vscode密码
            vscode_passwd = Column(String, nullable=False)
            # tensorboardPort，tensorboard端口
            tensorboard_port = Column(String, nullable=False)
            # # customPort，自定义端口
            # custom_port = Column(String, nullable=True)
            # sitonAiToolPort，sitonAiTool端口
            siton_ai_tool_port = Column(String, nullable=False)
            # note，备注
            note = Column(String, nullable=True)

            # userId，用户id
            user_id = Column(String, ForeignKey('users.user_id'), nullable=False)

            user = relationship('Users', back_populates='tasks')

            def to_risc_dict(self):
                return {
                    'name': self.name,
                    'note': self.note,
                    'status': self.str_status,
                    'last update': self.update_time,
                    'release time': self.release_time,
                }

            # @hybrid_property
            # def status(self):
            #     # 确保 __status 是整数
            #     status_code = getattr(self, '__status', None)
            #     if status_code is not None and isinstance(status_code, str):
            #         return STATUS_MAP.get(status_code, 'Unknown Status')
            #     return 'Unknown Status'
            #
            # @status.setter
            # def status(self, status_code):
            #     self.__status = status_code
            @property
            def str_status(self):
                return STATUS_MAP.get(int(self.status), 'Unknown Status')

        return Tasks

    def __reg_configs(self):
        BASE = self.__Base

        class Configs(BASE):
            __tablename__ = 'configs'
            id = Column(Integer, primary_key=True, autoincrement=True)
            key = Column(String, nullable=False)
            value = Column(String, nullable=False)

        return Configs


class DML:
    def __init__(self):
        self.__ddl = DDL()
        self.__Session = sessionmaker(bind=self.__ddl.ENGINE)
        self.__session = self.__Session()
        self.__Tables = self.__ddl.Tables

    def query(self, table, condition):
        if condition is None:
            return self.__session.query(table).all()

        return self.__session.query(table).filter(condition).all()

    def insert(self, table, **kwargs):
        self.__session.add(table(**kwargs))
        self.__session.commit()

    def update(self, table, condition, **kwargs):
        self.__session.query(table).filter(condition).update(kwargs)
        self.__session.commit()

    def delete(self, table, condition):
        self.__session.query(table).filter(condition).delete()
        self.__session.commit()

    def insert_user(self, account, password):
        self.insert(self.Tables['Users'], account=account, password=password)

    def update_user_token(self, account, token):
        table = self.Tables['Users']
        self.update(table, table.account == account, token=token)

    def __update_user_info(self, account: str, user_id: str, phone: str):
        table = self.Tables['Users']
        self.update(table, table.account == account, phone=phone, user_id=user_id)

    def query_user(self, account):
        table = self.Tables['Users']
        result = self.query(table, table.account == account)
        return result[0] if result and not result == [] else None

    def query_all_users(self):
        return self.query(self.Tables['Users'], None)

    def insert_record(self, record: dict):
        table = self.Tables['Tasks']
        # 首先保存用户信息
        self.__update_user_info(record['email'], record['userId'], record['phone'])
        # 然后保存任务信息
        params = {
            "id": record['id'],
            "name": record['taskName'],
            "status": record['status'],
            "release_time": record['releaseTime'],
            "update_time": record['updateTime'],
            "agent_ip": record['agentIp'],
            "ssh_port": record['sshPort'],
            "ssh_passwd": record['sshPasswd'],
            "jupyter_port": record['jupyterPort'],
            "jupyter_passwd": record['jupyterPasswd'],
            "vnc_port": record['vncPort'],
            "vnc_passwd": record['vncPasswd'],
            "vscode_port": record['vscodePort'],
            "vscode_passwd": record['vscodePasswd'],
            "tensorboard_port": record['tensorboardPort'],
            # "custom_port": record['customPort'],
            "siton_ai_tool_port": record['sitonAiToolPort'],
            "note": record['note'],
            "user_id": record['userId']
        }
        if self.query(table, table.id == record['id']):
            # 如果任务已存在，则更新
            self.update(table, table.id == record['id'], **params)
        else:
            self.insert(table, **params)

    def insert_records(self, records: list[dict]):
        for record in records:
            self.insert_record(record)

    def delete_record(self, taskId: str):
        self.delete(self.Tables['Tasks'], self.Tables['Tasks'].id == taskId)

    def delete_records(self, taskIds: list[str]):
        for taskId in taskIds:
            self.delete_record(taskId)

    def update_config(self, key: str, value: str):
        table = self.Tables['Configs']
        if self.query(table, table.key == key):
            self.update(table, table.key == key, value=value)
        else:
            self.insert(table, key=key, value=value)

    def query_config(self, key: str) -> str:
        """
        :param key: key of config
        :return: value of config
        """
        r = self.query(self.Tables['Configs'], self.Tables['Configs'].key == key)
        return r[0].value if r else None

    def delete_config(self, key: str):
        self.delete(self.Tables['Configs'], self.Tables['Configs'].key == key)

    def query_record(self, taskId: str):
        return self.query(self.Tables['Tasks'], self.Tables['Tasks'].id == taskId)[0]

    def query_all_record(self):
        return self.query(self.Tables['Tasks'], None)

    def close(self):
        self.__ddl.ENGINE.dispose()

    @property
    def Tables(self):
        return self.__Tables
