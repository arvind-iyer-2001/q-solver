FROM ubuntu:22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y curl unzip ncurses-bin && rm -rf /var/lib/apt/lists/*
RUN curl -sLO https://portal.dl.kx.com/assets/raw/kdb-x/install_kdb/~latest~/install_kdb.sh &&     bash install_kdb.sh -y --b64lic 'C6cAJ27yCfLWhmYJbtNb/ItRR/P45qUckqKufZx33igNcXP6ITzEpp7OBiOLVsutXzGfnj1fQoEpovgMLNroOTp/7Ur0LFcpiNsbdpDInW06gcA9fcb5kT8Q4NJ9XiOkjBPn2Rq1QqQDYYft6naBR9QN+l9ls9X+MgyCUg/afvuAba3yY9oB+8jjGYKbrDpfDPCtW6FT6O5b/nd3Sli1vsK5PnSUFv1WprsFmvrR4jCXAvk8GXhIMd4lVjJX088KW89woEMkqzA7ecwWdIBgKgYql/fEnTWJQTaMmV0V4Ud90QOLZXluw8Pmwjc/NBOKj03WcwSLcAT8kMwEeXx1ovMeBZOUs82uVPIFEDK9/qKOVT9U1gdG6Bj7lyPHLVU10yd32X42qyfalVrclECwMFUOXtswJMn7/j5sLqegjDPDwLBITlSfe6mOznFE3jlNZAubgRbJg5EPldLqgJeiW1WE4kr5MGydWB/njs+cKwLM9+AOjKnPVZtRVT03SQqHKMEZLrHvL4hulYe6qJjhIKpzdJS2bh4kVP/+1F+qMp+6dNAI/U1MpCqKOUcOB9NOag==' &&     rm install_kdb.sh

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y ncurses-bin && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.kx/bin /root/.kx/bin
COPY --from=builder /root/.kx/mod /root/.kx/mod
