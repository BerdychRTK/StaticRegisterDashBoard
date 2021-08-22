import re
import xlrd
import dataclasses
import uuid
import enum
import warnings
import json
import sys
from typing import List, Any, Union

from xlrd.biffh import XL_CELL_BLANK

INDEX = "chip_index"
RESERVED = "reserved"
A = 0
B = 1
C = 2
D = 3
E = 4
F = 5
G = 6
H = 7
I = 8
J = 9
K = 10
L = 11
M = 12
N = 13
O = 14
P = 15
Q = 16
R = 17
S = 18
T = 19


class Stage(enum.Enum):
    attributes = 0
    data_mux_file = 1
    memory_block = 2
    revisions = 3
    data_mux = 4
    register = 5


def searchForReplacement(repl: str, filename: str, output: str):
    regexp = re.compile(r"JSON\.parse\('\{.*\}'\)")
    with open(filename, "r") as src:
        content = src.read()
        target = regexp.findall(content)
        if not target:
            raise ValueError()
        with open(f"{output}.html", "w") as dump:
            dump.write(
                content.replace(target[0], repl, 1),
            )


def create_uid() -> str:
    return str(uuid.uuid4())


def toHex(value: int, bitWidth=32):
    if not isinstance(value, int):
        raise TypeError(f"expecting integer type: got {type(value)}")
    return f"0x{value:0{bitWidth//4}X}"


@dataclasses.dataclass
class MemoryBlock:
    name: str
    baseAddress: Union[str, int]
    number: Any
    desc: str
    belongTo: str


@dataclasses.dataclass
class Field:
    bits: str = ""
    field: str = ""
    default: str = ""
    access: str = ""
    desc: str = ""
    id: str = dataclasses.field(default_factory=create_uid)


@dataclasses.dataclass
class Register:
    address: str
    offset: str
    name: str
    desc: str = ""
    id: str = dataclasses.field(default_factory=create_uid)
    fields: List[Field] = dataclasses.field(default_factory=list)

    def addFieldByRow(self, row: List[xlrd.sheet.Cell]):
        self.fields.append(
            Field(
                bits=f"{int(row[L].value)}:{int(row[M].value)}",
                field=row[N].value,
                access=row[Q].value,
                default=row[R].value,
                desc=row[P].value,
            )
        )

    def runLint(self, bitWidth=32):
        totalbits = 0
        for field in self.fields:
            bits = field.bits
            msb, lsb = bits.split(":")
            totalbits += int(msb) - int(lsb) + 1
        if totalbits != bitWidth:
            for field in self.fields:
                print(field.field, field.name)
            raise ValueError(
                f"{self.name}: expecting BitWidth = {bitWidth}, got {totalbits} instead"
            )


@dataclasses.dataclass
class Node:
    name: str = ""
    address: str = ""
    id: str = dataclasses.field(default_factory=create_uid)
    children: List[Register] = dataclasses.field(default_factory=list)


class ExcelParser:
    def __init__(self, excelFile: str):
        self.workbook = xlrd.open_workbook(excelFile)
        self.root = Node(name="root", address="")
        self.index = {
            "headpage": "",
            "prefix": "",
            "pprange": "",
            "name": "",
            Stage.data_mux_file: [],
            Stage.memory_block: [],
            Stage.revisions: [],
        }
        self.hasIndex = any(
            filter(lambda name: name.lower() == INDEX, self.workbook.sheet_names())
        )
        if self.hasIndex:
            self.readIndex()
            self.sheets = self.index[Stage.data_mux_file]
        else:
            self.sheets = filter(
                lambda name: name.lower().startswith("mod_"),
                self.workbook.sheet_names(),
            )

        # for sheet in ["mod_SYS_REG"]:
        #     self.root.children.append(self.createNode(sheet))

    def createTree(self) -> Node:
        for sheet in self.sheets:
            self.root.children.append(self.createNode(sheet))
        self.root.name = self.index["headpage"]
        return self.root

    def readIndex(self):
        index: xlrd.sheet.Sheet = self.workbook.sheet_by_name(INDEX)
        stage = Stage.attributes
        skipRow = 0
        for row in index:

            if skipRow:
                skipRow -= 1
                continue
            rowIndex = str(row[A].value or "").strip().lower()

            if stage == Stage.attributes:
                if rowIndex == "data_mux_file":
                    stage = Stage.data_mux_file
                    continue
                if rowIndex in self.index:
                    self.index[rowIndex] = row[B].value

            elif stage == Stage.data_mux_file:
                if rowIndex == "memory_block":
                    stage = Stage.memory_block
                    skipRow = 1

                xml = str(row[B].value)
                if xml.endswith(".xml"):
                    self.index[stage].append(xml)

            elif stage == Stage.memory_block:
                if rowIndex == "history":
                    stage = Stage.revisions
                    skipRow = 1

                self.index[stage].append(
                    MemoryBlock(
                        name=row[A].value,
                        baseAddress=row[B].value,
                        number=row[C].value,
                        desc=row[D].value,
                        belongTo=row[E].value,
                    )
                )
            elif stage == Stage.revisions:
                pass
            else:
                raise IndexError(f"not expecting this stage: {stage}")

    def getSheetByName(self, name: str) -> xlrd.sheet.Sheet:
        return self.workbook.sheet_by_name(name.replace(".xml", ""))

    def createNode(self, sheetName: str):
        sheet = self.getSheetByName(sheetName)
        isLeaf = sheet.row(0)[A].value.lower() == "file"

        if isLeaf:
            return self.createLeaf(sheetName)

        node = Node()
        stage = Stage.attributes
        for row in sheet:
            rowIndex = str(row[A].value or "").strip().lower()
            rowB = str(row[B].value or "")
            if stage == Stage.attributes:
                if rowIndex == "reg_file":
                    stage = Stage.data_mux
                    continue
                node.__setattr__(rowIndex, rowB)

            elif stage == Stage.data_mux:
                child = rowB
                if child.lower().startswith("file_"):
                    child = self.createLeaf(child)
                elif child.lower().startswith("mode_"):
                    child = self.createNode(child)
                else:
                    raise SyntaxError(f"Expecting file_ or mode_, got {rowB} instead")

                node.children.append(child)

        if len(node.children) == 1:
            return node.children[0]
        return node

    def createLeaf(self, sheetName: str):
        sheet = self.getSheetByName(sheetName)
        node = Node()
        stage = Stage.attributes
        skipRow = 0
        baseAddr = 0
        offset = 0
        for row in sheet:
            if skipRow:
                skipRow -= 1
                continue

            rowIndex = str(row[A].value or "").strip().lower()
            rowB = str(row[B].value or "")
            if stage == Stage.attributes:
                if rowIndex == "register":
                    baseAddr = self.getBaseAddress(sheetName, node)
                    skipRow = 1
                    stage = Stage.register
                    bitWidth = getattr(node, "BitWidth", 32)
                    continue
                node.__setattr__(rowIndex, rowB)
            elif stage == Stage.register:
                rowA = rowIndex

                if rowIndex in ("register", "table"):
                    skipRow = 1
                    continue

                if rowA:
                    register = Register(
                        name=rowB,
                        address=toHex(baseAddr + offset),
                        offset=toHex(offset, 16),
                        desc=row[J].value,
                    )
                    offset += (
                        int(row[H].value or bitWidth) * (int(row[G].value or 0) + 1)
                    ) // 8

                if row[M].ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
                    continue
                register.addFieldByRow(row)

                if int(row[M].value) == 0:
                    if register.name.lower() != RESERVED:
                        register.runLint(bitWidth)
                        node.children.append(register)
            else:
                raise IndexError(f"not expecting this stage: {stage}")
        return node

    def getBaseAddress(self, sheetName: str, node: Node) -> int:

        name = sheetName.replace("file_", "").replace(".xml", "")
        baseAddr = 0
        if not self.hasIndex:
            baseAddr = getattr(node, "abstract", 0) or 0
        else:
            try:
                block: MemoryBlock = next(
                    filter(
                        lambda block: block.name == name,
                        self.index[Stage.memory_block],
                    )
                )
                baseAddr = block.baseAddress
            except StopIteration:
                warnings.warn(f"This name not found in memory block: {node.name}")

        if isinstance(baseAddr, str):
            return int(baseAddr, 16)

        return int(baseAddr)


def parse_arg():
    if len(sys.argv) == 1:
        print("Error: Not enough argument")
        print(f"    usage: python {sys.argv[0]} filename")
        sys.exit(1)
    return sys.argv[1]


def main():
    filename = parse_arg()
    parser = ExcelParser(filename)
    root = parser.createTree()
    searchForReplacement(
        json.dumps(dataclasses.asdict(root)),
        "./template/index.html",
        output=root.name,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
